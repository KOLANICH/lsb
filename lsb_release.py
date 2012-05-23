#!/usr/bin/python

# LSB release detection module for Debian
# (C) 2005-10 Chris Lawrence <lawrencc@debian.org>

#    This package is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; version 2 dated June, 1991.

#    This package is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.

#    You should have received a copy of the GNU General Public License
#    along with this package; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
#    02110-1301 USA

# Python3-compatible print() function
from __future__ import print_function

import sys
import commands
import os
import re

# XXX: Update as needed
# This should really be included in apt-cache policy output... it is already
# in the Release file...
RELEASE_CODENAME_LOOKUP = {
    '1.1' : 'buzz',
    '1.2' : 'rex',
    '1.3' : 'bo',
    '2.0' : 'hamm',
    '2.1' : 'slink',
    '2.2' : 'potato',
    '3.0' : 'woody',
    '3.1' : 'sarge',
    '4.0' : 'etch',
    '5.0' : 'lenny',
    '6.0' : 'squeeze',
    '7.0' : 'wheezy',
    }

TESTING_CODENAME = 'unknown.new.testing'

RELEASES_ORDER = RELEASE_CODENAME_LOOKUP.items()
RELEASES_ORDER.sort()
RELEASES_ORDER = list(zip(*RELEASES_ORDER)[1])
RELEASES_ORDER.extend(['stable', 'testing', 'unstable', 'sid'])

def lookup_codename(release, unknown=None):
    m = re.match(r'(\d+)\.(\d+)(r(\d+))?', release)
    if not m:
        return unknown

    shortrelease = '%s.%s' % m.group(1,2)
    return RELEASE_CODENAME_LOOKUP.get(shortrelease, unknown)

# LSB compliance packages... may grow eventually
PACKAGES = 'lsb-core lsb-cxx lsb-graphics lsb-desktop lsb-languages lsb-multimedia lsb-printing lsb-security'

modnamere = re.compile(r'lsb-(?P<module>[a-z0-9]+)-(?P<arch>[^ ]+)(?: \(= (?P<version>[0-9.]+)\))?')

def valid_lsb_versions(version, module):
    # If a module is ever released that only appears in >= version, deal
    # with that here
    if version == '3.0':
        return ['2.0', '3.0']
    elif version == '3.1':
        if module in ('desktop', 'qt4'):
            return ['3.1']
        elif module == 'cxx':
            return ['3.0', '3.1']
        else:
            return ['2.0', '3.0', '3.1']
    elif version == '3.2':
        if module == 'desktop':
            return ['3.1', '3.2']
        elif module == 'qt4':
            return ['3.1']
        elif module in ('printing', 'languages', 'multimedia'):
            return ['3.2']
        elif module == 'cxx':
            return ['3.0', '3.1', '3.2']
        else:
            return ['2.0', '3.0', '3.1', '3.2']
    elif version == '4.0':
        if module == 'desktop':
            return ['3.1', '3.2', '4.0']
        elif module == 'qt4':
            return ['3.1']
        elif module in ('printing', 'languages', 'multimedia'):
            return ['3.2', '4.0']
        elif module == 'security':
            return ['4.0']
        elif module == 'cxx':
            return ['3.0', '3.1', '3.2', '4.0']
        else:
            return ['2.0', '3.0', '3.1', '3.2', '4.0']
    elif version == '4.1':
        if module == 'desktop':
            return ['3.1', '3.2', '4.0', '4.1']
        elif module == 'qt4':
            return ['3.1']
        elif module in ('printing', 'languages', 'multimedia'):
            return ['3.2', '4.0', '4.1']
        elif module == 'security':
            return ['4.0', '4.1']
        elif module == 'cxx':
            return ['3.0', '3.1', '3.2', '4.0', '4.1']
        else:
            return ['2.0', '3.0', '3.1', '3.2', '4.0', '4.1']


    return [version]

try:
    set # introduced in 2.4
except NameError:
    import sets
    set = sets.Set

# This is Debian-specific at present
def check_modules_installed():
    # Find which LSB modules are installed on this system
    output = commands.getoutput("dpkg-query -f '${Version} ${Provides}\n' -W %s 2>/dev/null" % PACKAGES)
    if not output:
        return []

    modules = set()
    for line in output.split(os.linesep):
        version, provides = line.split(' ', 1)
        # Debian package versions can be 3.2-$REV, 3.2+$REV or 3.2~$REV.
        version = re.split('[-+~]', version, 1)[0]
        for pkg in provides.split(','):
            mob = modnamere.search(pkg)
            if not mob:
                continue

            mgroups = mob.groupdict()
            # If no versioned provides...
            if mgroups.get('version'):
                module = '%(module)s-%(version)s-%(arch)s' % mgroups
                modules.add(module)
            else:
                module = mgroups['module']
                for v in valid_lsb_versions(version, module):
                    mgroups['version'] = v
                    module = '%(module)s-%(version)s-%(arch)s' % mgroups
                    modules.add(module)

    modules = list(modules)
    modules.sort()
    return modules

longnames = {'v' : 'version', 'o': 'origin', 'a': 'suite',
             'c' : 'component', 'l': 'label'}

def parse_policy_line(data):
    retval = {}
    bits = data.split(',')
    for bit in bits:
        kv = bit.split('=', 1)
        if len(kv) > 1:
            k, v = kv[:2]
            if k in longnames:
                retval[longnames[k]] = v
    return retval

def compare_release(x, y):
    suite_x = x[1].get('suite')
    suite_y = y[1].get('suite')

    if suite_x and suite_y:
        if suite_x in RELEASES_ORDER and suite_y in RELEASES_ORDER:
            return RELEASES_ORDER.index(suite_y)-RELEASES_ORDER.index(suite_x)
        else:
            return cmp(suite_x, suite_y)

    return 0

def parse_apt_policy():
    data = []
    
    policy = commands.getoutput('LANG=C apt-cache policy 2>/dev/null')
    for line in policy.split('\n'):
        line = line.strip()
        m = re.match(r'(-?\d+)', line)
        if m:
            priority = int(m.group(1))
        if line.startswith('release'):
            bits = line.split(' ', 1)
            if len(bits) > 1:
                data.append( (priority, parse_policy_line(bits[1])) )

    return data

def guess_release_from_apt(origin='Debian', component='main',
                           ignoresuites=('experimental'),
                           label='Debian',
                           alternate_olabels={'Debian Ports':'ftp.debian-ports.org'}):
    releases = parse_apt_policy()

    if not releases:
        return None

    # We only care about the specified origin, component, and label
    releases = [x for x in releases if (
        x[1].get('origin', '') == origin and
        x[1].get('component', '') == component and
        x[1].get('label', '') == label) or (
        x[1].get('origin', '') in alternate_olabels and
        x[1].get('label', '') == alternate_olabels.get(x[1].get('origin', '')))]

    # Check again to make sure we didn't wipe out all of the releases
    if not releases:
        return None
    
    releases.sort()
    releases.reverse()

    # We've sorted the list by descending priority, so the first entry should
    # be the "main" release in use on the system

    max_priority = releases[0][0]
    releases = [x for x in releases if x[0] == max_priority]
    releases.sort(compare_release)

    return releases[0][1]

def guess_debian_release():
    distinfo = {'ID' : 'Debian'}

    kern = os.uname()[0]
    if kern in ('Linux', 'Hurd', 'NetBSD'):
        distinfo['OS'] = 'GNU/'+kern
    elif kern == 'FreeBSD':
        distinfo['OS'] = 'GNU/k'+kern
    elif kern in ('GNU/Linux', 'GNU/kFreeBSD'):
        distinfo['OS'] = kern
    else:
        distinfo['OS'] = 'GNU'

    distinfo['DESCRIPTION'] = '%(ID)s %(OS)s' % distinfo

    etc_debian_version = os.environ.get('LSB_ETC_DEBIAN_VERSION','/etc/debian_version')
    if os.path.exists(etc_debian_version):
        try:
            with open(etc_debian_version) as debian_version:
                release = debian_version.read().strip()
        except IOError as msg:
            print('Unable to open ' + etc_debian_version + ':', str(msg), file=sys.stderr)
            release = 'unknown'
            
        if not release[0:1].isalpha():
            # /etc/debian_version should be numeric
            codename = lookup_codename(release, 'n/a')
            distinfo.update({ 'RELEASE' : release, 'CODENAME' : codename })
        elif release.endswith('/sid'):
            if release.rstrip('/sid').lower().isalpha() != 'testing':
                global TESTING_CODENAME
                TESTING_CODENAME = release.rstrip('/sid')
            distinfo['RELEASE'] = 'testing/unstable'
        else:
            distinfo['RELEASE'] = release

    # Only use apt information if we did not get the proper information
    # from /etc/debian_version or if we don't have a codename
    # (which will happen if /etc/debian_version does not contain a
    # number but some text like 'testing/unstable' or 'lenny/sid')
    #
    # This is slightly faster and less error prone in case the user
    # has an entry in his /etc/apt/sources.list but has not actually
    # upgraded the system.
    if not distinfo.get('CODENAME'):
      rinfo = guess_release_from_apt()
      if rinfo:
        release = rinfo.get('version')

        # Special case Debian-Ports as their Release file has 'version': '1.0'
        if release == '1.0' and rinfo.get('origin') == 'Debian Ports' and rinfo.get('label') == 'ftp.debian-ports.org':
            release = None
            rinfo.update({'suite': 'unstable'})

        if release:
            codename = lookup_codename(release, 'n/a')
        else:
            release = rinfo.get('suite', 'unstable')
            if release == 'testing':
                # Would be nice if I didn't have to hardcode this.
                codename = TESTING_CODENAME
            else:
                codename = 'sid'
        distinfo.update({ 'RELEASE' : release, 'CODENAME' : codename })

    if distinfo.get('RELEASE'):
        distinfo['DESCRIPTION'] += ' %(RELEASE)s' % distinfo
    if distinfo.get('CODENAME'):
        distinfo['DESCRIPTION'] += ' (%(CODENAME)s)' % distinfo

    return distinfo

# Whatever is guessed above can be overridden in /etc/lsb-release
def get_lsb_information():
    distinfo = {}
    etc_lsb_release = os.environ.get('LSB_ETC_LSB_RELEASE','/etc/lsb-release')
    if os.path.exists(etc_lsb_release):
        try:
            with open(etc_lsb_release) as lsb_release_file:
                for line in lsb_release_file:
                    line = line.strip()
                    if not line:
                        continue
                    # Skip invalid lines
                    if not '=' in line:
                        continue
                    var, arg = line.split('=', 1)
                    if var.startswith('DISTRIB_'):
                        var = var[8:]
                        if arg.startswith('"') and arg.endswith('"'):
                            arg = arg[1:-1]
                        if arg: # Ignore empty arguments
                            distinfo[var] = arg.strip()
        except IOError as msg:
            print('Unable to open ' + etc_lsb_release + ':', str(msg), file=sys.stderr)
            
    return distinfo

def get_distro_information():
    lsbinfo = get_lsb_information()
    # OS is only used inside guess_debian_release anyway
    for key in ('ID', 'RELEASE', 'CODENAME', 'DESCRIPTION',):
        if key not in lsbinfo:
            distinfo = guess_debian_release()
            distinfo.update(lsbinfo)
            return distinfo
    else:
        return lsbinfo

def test():
    print(get_distro_information())
    print(check_modules_installed())

if __name__ == '__main__':
    test()
