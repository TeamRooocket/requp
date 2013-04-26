#!/usr/bin/env python
# import os
import sys
import ConfigParser
import re
import argparse
import subprocess
from collections import OrderedDict, namedtuple

PYPI_RE = re.compile(r'^(?P<name>[\w\-_]+)(?P<op>[<>=]+)(?P<version>[\w\.]+)$')
EDITABLE_RE = re.compile(
    r'^-e .*@(?P<version>[\w\.]+)#egg=(?P<name>[\w\-_]+)$')

ReqLine = namedtuple('ReqLine', 'no, line, type, name, op, version')


def venv_db():
    pips = subprocess.check_output(["pip", "freeze"]).splitlines()
    db = OrderedDict()
    for line in pips:
        if line.startswith('-e'):
            match = EDITABLE_RE.match(line)
        else:
            match = PYPI_RE.match(line)
        if match:
            result = match.groupdict()
        name, version = result['name'].lower(), result['version']
        db.setdefault(name, {
            'version': version,
            'requires': [],
            'refs': [],
            'line': line})

    cmd = ['pip', 'show']
    cmd.extend(db.keys())
    lines = filter(
        lambda s: s.startswith('Requires') or s.startswith('Name'),
        subprocess.check_output(
            cmd).splitlines())
    lines = iter(lines)
    while True:
        try:
            name = lines.next().replace('Name: ', '').strip().lower()
            requires = filter(lambda s: s, map(
                lambda s: s.strip().lower(),
                lines.next().replace('Requires: ', '').split(', ')))
            db[name]['requires'] = requires
            for req in requires:
                if req in db:
                    db[req]['refs'].append(name)
        except StopIteration:
            break
    return db


def parse_req(line_tuple):
    no, line = line_tuple
    line = line.strip()
    line_type, name, version, op = 'text', None, None, None
    if line.startswith('-e'):
        match = EDITABLE_RE.match(line)
        line_type = match and 'editable' or line_type
    else:
        match = PYPI_RE.match(line)
        line_type = match and 'dist' or line_type
    if not match and line.startswith('#'):
        xline = line[1:].strip()
        if xline.startswith('-e'):
            match = EDITABLE_RE.match(xline)
            line_type = match and 'ceditable' or line_type
        else:
            match = PYPI_RE.match(xline)
            line_type = match and 'cdist' or line_type
    if match:
        result = match.groupdict()
        name, version = result['name'].lower(), result['version']
        op = result.get('op', '==')
    return ReqLine(no, line, line_type, name, op, version)


def print_freeze(db, ignore, is_uncomment=False):
    """
    Simply prints all packages and comments those that are required
    by other packages.
    """
    refered = 0
    for name, data in db.iteritems():
        if name in ignore:
            continue
        if not data['refs']:
            print data['line']
        else:
            refered += 1
    if not refered:
        return
    for name, data in db.iteritems():
        if name in ignore:
            continue
        if data['refs']:
            if is_uncomment:
                print data['line']
            else:
                print '# ' + data['line']
            print '# required by: {}'.format(", ".join(data['refs']))


def interactive_freeze(
    db, req_types, req_buffer, ignore,
        skip=None, is_uncomment=False):
    """
    This function aims to help categorize packages,
    when you initially create your requirement files.
    """
    skip = skip or set()
    ignore = set() | ignore
    _prt = ", ".join(["({}){}".format(
        i and i+1 or 'Enter', value) for i, value in enumerate(req_types)])
    prompt = '(i)gnore, {}> '.format(_prt)
    if is_uncomment:
        prompt_ref = '(i)gnore, (Enter)pass> '
    else:
        prompt_ref = '(i)gnore, (Enter)pass, (u)ncomment and pass> '
    req_sets = [set() for req in req_types]
    for name, data in db.iteritems():
        if name in ignore or name in skip:
            continue
        if not data['refs']:
            while True:
                print data['line']
                r = raw_input(prompt)
                if r.lower().startswith('i'):
                    ignore.add(name)
                    break
                else:
                    try:
                        if r == '':
                            choice = 0
                        else:
                            choice = int(r) - 1
                        if choice >= 0 and choice < len(req_types):
                            req_buffer[choice].append(data['line'])
                            req_sets[choice].add(name)
                            break
                        else:
                            print 'invalid choice'
                    except ValueError:
                        print 'invalid choice'

    for name, data in db.iteritems():
        if name in ignore or name in skip:
            continue
        if data['refs']:
            choice = None
            for num, req_set in enumerate(req_sets):
                for ref in data['refs']:
                    if ref in req_set:
                        choice = num
                        break
                if choice is not None:
                    break
            if choice is None:
                choice = 0
            while True:
                if is_uncomment:
                    print data['line']
                else:
                    print '# ' + data['line']
                print ("# required by: \033[92m{}\033[0m").format(
                    ", ".join(data['refs']))
                print "this will be added to \033[92m{}\033[0m".format(
                    req_types[choice])
                r = raw_input(prompt_ref).lower()
                uncomment = False or is_uncomment
                if r.startswith('i'):
                    ignore.add(name)
                    break
                else:
                    if r.startswith('u'):
                        uncomment = True
                        r = r[1:]
                    if r == '':
                        if uncomment:
                            line = data['line']
                        else:
                            line = '# ' + data['line']
                        req_buffer[choice].append(line)
                        req_buffer[choice].append(
                            '# required by: ' + ", ".join(data['refs']))
                        req_sets[choice].add(name)
                        break
                    else:
                        print 'invalid choice'
    print '=' * 40
    print 'RESULTS'
    print '=' * 40
    for num, buf in enumerate(req_buffer):
        if len(buf):
            print '# ' + req_types[num] + ' ' + str()
            print "\n".join(buf)
            print

    print '# ignored'
    print ", ".join(ignore)
    return ignore


def update_requirements(db, reqs, filenames, ignore):
    mentioned = set()
    for num, req in enumerate(reqs):
        print 'checking {}'.format(filenames[num])
        missing = False
        for line in req:
            if line.type == 'text':
                continue
            name, op, version = line.name, line.op, line.version
            if name == 'pip':
                continue
            if name in db:
                mentioned.add(name)
                if name in ignore:
                    print (
                        "\033[93m{} is required and ignored"
                        " at the same time. Check you "
                        "config file.\033[0m").format(name)
                installed_version = db[name]['version']
                refs = db[name]['refs']
                test = False
                if op == '==':
                    test = installed_version == version
                elif op == '<=':
                    test = installed_version <= version
                elif op == '>=':
                    test = installed_version >= version
                if test is False:
                    update = True
                    print (
                        "\033[91mInstalled version of {name} does not "
                        "match: installed {installed_version}, "
                        "required {op}{version}\nHandle this issue "
                        "yourself!\033[0m"
                    ).format(
                        name=name,
                        installed_version=installed_version,
                        op=op,
                        version=version)
                else:
                    print (
                        "\033[92mmatch: {}{name} {installed_version}"
                        "{op}{version}\033[0m").format(
                            line.type.startswith('c') and '#' or '',
                            name=name,
                            installed_version=installed_version,
                            op=op,
                            version=version)
                if refs and not line.type.startswith('c'):
                    print (
                        "\033[93m{name} might be excluded; required by "
                        "[{refs}]\033[0m").format(
                            name=name, refs=", ".join(refs))
            else:
                missing = True
                print (
                    "\033[91m{name}{op}{version} is "
                    "not installed\033[0m").format(
                        name=name, op=op, version=version)
        if missing:
            print "You might want to run:"
            print "\t\033[91mpip install -r {}\033[0m".format(filenames[num])
    return mentioned


def save_ignore(filename, config, ignore):
    config.set('requp', 'ignore', " ".join(ignore))
    f = open(filename, 'wb')
    config.write(f)
    f.close()


def _get(config, option, default=None):
    try:
        if config is None:
            return default
        v = config.get('requp', option)
        if v is None:
            return default
        return v
    except ConfigParser.NoOptionError:
        return default


def main():
    parser = argparse.ArgumentParser(
        description="Utility updating requires.txt", add_help=True)

    parser.add_argument(
        '--config-file', '-c', default='.requp.cfg', dest='file',
        help='File containing requirements. Default: .requp.cfg',
        required=False)
    # parser.add_argument(
    #     '--dry-run', '-n', default=False, dest='dryrun',
    #     help='Run the command without actual changes',
    #     required=False, action='store_true')
    parser.add_argument(
        '--freeze', '-f', default=False, dest='freeze',
        help='Print out requirements that are needed',
        required=False, action='store_true')
    parser.add_argument(
        '--interactive', '-i', default=False, dest='is_inter',
        help='Print out requirements that are needed',
        required=False, action='store_true')
    parser.add_argument(
        '--uncomment', '-u', default=False, dest='is_uncomment',
        help='Uncomment packages required by other packages',
        required=False, action='store_true')
    args = parser.parse_args()

    config = ConfigParser.ConfigParser()
    try:
        config.readfp(open(args.file))
    except IOError:
        print ('There is no such file: {}'.format(args.file))
        return

    db = venv_db()
    req_types = _get(config, 'req_types')
    req_types = req_types and req_types.split(' ') or ['prod']
    ignore = _get(config, 'ignore')
    ignore = ignore and {x.strip() for x in ignore.split(" ") if x.strip()} or set()
    if args.freeze:
        if args.is_inter:
            req_files = []
            for req_type in req_types:
                filename = _get(config, req_type)
                assert filename, (
                    'requirements filename is not specified for {}'
                ).format(req_type)
                req_files.append(open(filename, 'wb'))
            req_buffer = [[] for req in req_types]
            result = interactive_freeze(
                db, req_types, req_buffer, ignore,
                is_uncomment=args.is_uncomment)
            r = raw_input('Save changes (y/n)? ')
            if r.lower().startswith('y'):
                ignore = result
                for num, buf in enumerate(req_buffer):
                    req_files[num].write("\n".join(buf))
                    req_files[num].close()
                save_ignore(args.file, config, ignore)
        else:
            print_freeze(db, ignore, is_uncomment=args.is_uncomment)
    else:
        reqs = []
        filenames = []
        req_files = []
        for req_type in req_types:
            filename = _get(config, req_type)
            assert filename, (
                'requirements filename is '
                'not specified for {}').format(req_type)
            filenames.append(filename)
            reqs.append(map(parse_req, enumerate(
                open(filename).readlines())))
            req_files.append(open(filename, 'a'))
        req_buffer = [[] for req in req_types]
        skip = update_requirements(db, reqs, filenames, ignore)
        print '=' * 40
        print 'Checking for new packages'
        print '=' * 40
        result = interactive_freeze(
            db, req_types, req_buffer, ignore, skip=skip,
            is_uncomment=args.is_uncomment)
        r = raw_input('Save changes (y/n)? ')
        if r.lower().startswith('y'):
            ignore = result
            for num, buf in enumerate(req_buffer):
                if len(buf):
                    buf.insert(0, '')
                    req_files[num].write("\n".join(buf))
                req_files[num].close()
            save_ignore(args.file, config, ignore)


if __name__ == "__main__":
    main()
