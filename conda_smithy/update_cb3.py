import io
import re
import jinja2
import os
import ruamel.yaml
import collections
import requests
import tempfile
import tarfile
import zipfile
from .utils import tmp_directory, render_meta_yaml

class Str(ruamel.yaml.scalarstring.ScalarString):
    __slots__ = ('lc')

    style = ""

    def __new__(cls, value):
        return ruamel.yaml.scalarstring.ScalarString.__new__(cls, value)

class MyPreservedScalarString(ruamel.yaml.scalarstring.PreservedScalarString):
    __slots__ = ('lc')

class MyDoubleQuotedScalarString(ruamel.yaml.scalarstring.DoubleQuotedScalarString):
    __slots__ = ('lc')

class MySingleQuotedScalarString(ruamel.yaml.scalarstring.SingleQuotedScalarString):
    __slots__ = ('lc')

class MyConstructor(ruamel.yaml.constructor.RoundTripConstructor):
    def construct_scalar(self, node):
        # type: (Any) -> Any
        if not isinstance(node, ruamel.yaml.nodes.ScalarNode):
            raise ruamel.yaml.constructor.ConstructorError(
                None, None,
                "expected a scalar node, but found %s" % node.id,
                node.start_mark)

        if node.style == '|' and isinstance(node.value, ruamel.yaml.compat.text_type):
            ret_val = MyPreservedScalarString(node.value)
        elif bool(self._preserve_quotes) and isinstance(node.value, ruamel.yaml.compat.text_type):
            if node.style == "'":
                ret_val = MySingleQuotedScalarString(node.value)
            elif node.style == '"':
                ret_val = MyDoubleQuotedScalarString(node.value)
            else:
                ret_val = Str(node.value)
        else:
            ret_val = Str(node.value)
        ret_val.lc = ruamel.yaml.comments.LineCol()
        ret_val.lc.line = node.start_mark.line
        ret_val.lc.col = node.start_mark.column
        return ret_val


class Section:
    def __init__(self, section, start, end):
        self.section = section
        self.start = start
        self.end = end

    def __getitem__(self, item):
        if item not in self.section:
            return None
        sect = self.section[item]
        start = sect.lc.line
        for other in self.section:
            if other.lc.line > start:
                end = other.lc.line
                return Section(sect, start, end)
        return Section(sect, start, self.end)

        
def iterate(tarzip):
    if isinstance(tarzip, zipfile.ZipFile):
        for f in iter(tarzip.infolist()):
            yield f
    elif isinstance(tarzip, tarfile.TarFile):
        for f in tarzip:
            yield f


def name(tzinfo):
    if isinstance(tzinfo, zipfile.ZipInfo):
        return tzinfo.filename
    elif isinstance(tzinfo, tarfile.TarInfo):
        return tzinfo.name


def get_compilers(url):
    '''
    Download the source and check for C/C++/Fortran
    Also check if `np.get_include()` is present in the setup.py files
    Return whether a C/C++/Fortran compiler is used and whether
    numpy headers are used.
    '''
    if isinstance(url, list):
        for u in url:
            r = requests.get(u, allow_redirects=True)
            if r.ok:
                url = u
                break
    else:
        r = requests.get(url, allow_redirects=True)
    fname = os.path.basename(url)
    ext = os.path.splitext(url)[1]
    if ext == '.zip':
        tarzip_open = zipfile.ZipFile
    else:
        tarzip_open = tarfile.open

    with tmp_directory() as tmp_dir:
        with open(os.path.join(tmp_dir, fname), 'wb') as f:
            f.write(r.content)
        need_numpy_pin = False
        with tarzip_open(os.path.join(tmp_dir, fname)) as tf:
            need_f = any([name(f).lower().endswith(('.f', '.f90', '.f77')) for f in iterate(tf)])
            # Fortran builds use CC to perform the link (they do not call the linker directly).
            need_c = True if need_f else \
                        any([name(f).lower().endswith(('.c', '.pyx')) for f in iterate(tf)])
            need_cxx = any([name(f).lower().endswith(('.cxx', '.cpp', '.cc', '.c++'))
                        for f in iterate(tf)])
            for f in iterate(tf):
                if name(f).lower().endswith('setup.py'):
                    try:
                        content = tf.extractfile(f).read().decode("utf-8")
                        if 'numpy.get_include()' in content or 'np.get_include()' in content:
                            need_numpy_pin = True
                    except:
                        pass
    return need_f, need_c, need_cxx, need_numpy_pin


def update_cb3(recipe_path, conda_build_config_path):
    '''
    Update the recipe in `recipe_path` to use conda-build=3 features according
    to conda-build config yaml in `conda_build_config_path`.
    Returns the updated recipe and a message about the changes made.
    '''
    yaml = ruamel.yaml.YAML()
    yaml.Constructor = MyConstructor
    yaml.allow_duplicate_keys = True

    with io.open(recipe_path, 'rt') as fh:
        lines = list(fh)
        orig_content = ''.join(lines)
        content = orig_content
        jinjas = re.findall('{%(?:.+?)%}', content, re.DOTALL)
        for j in jinjas:
            new_j = ''
            for c in j:
                if c == '\n':
                    new_j += '\n'
                else:
                    new_j += ' '
            content = content.replace(j, new_j)
        content = render_meta_yaml(content)
        content2 = render_meta_yaml(orig_content)
        meta_ = yaml.load(content)
        orig_meta = yaml.load(content2)
        content2 = content2.split('\n')

    change_lines = {}

    meta = Section(meta_, 0, len(content.split('\n')))
    build_section = meta['build']
    messages = collections.OrderedDict()

    requirements_section = meta['requirements']
    if not requirements_section:
        return orig_content, ''

    reqbuild_section = requirements_section['build']
    if not reqbuild_section:
        return orig_content, ''

    reqbuild_s = reqbuild_section.start
    reqbuild_line = lines[reqbuild_s-1]

    messages['Renamed build with host'] = True
    change_lines[reqbuild_s-1] = (reqbuild_line, reqbuild_line.replace('build:', 'host:'))

    url = orig_meta['source']['url']
    need_f, need_c, need_cxx, need_numpy_pin = get_compilers(url)
    #need_f, need_c, need_cxx, need_numpy_pin = False, False, False, False
    need_mingw_c = False
    is_r_package = False

    with io.open(conda_build_config_path, 'r') as fh:
        config = ''.join(fh)
        ind = config.index('# Pinning packages')
        config = config[ind:]
        config = yaml.load(config)

    pinned_packages = list(config.keys())
    build_lines = []
    build_space = ''
    need_boost_pin = False
    python_win_matrix = False
    python_dep = False
    section = 'build'
    reqs = {'build': [], 'run': []}

    # Setup requirements
    for i in range(requirements_section.start, requirements_section.end+1):
        line = lines[i].strip()
        if line == 'run:':
            section = 'run'
        if line.startswith('- '):
            line = content2[i].strip()[2:].strip()
            req = line.split(' ')[0]
            reqs[section].append(req)

    section = 'build'

    # Remove build stuff
    for i in range(requirements_section.start, requirements_section.end+1):
        line = lines[i].strip()
        if line == 'run:':
            section = 'run'
        if line.startswith('- '):
            build_space = ' ' * (len(lines[i]) - len(lines[i].lstrip())) + '- '
            line = lines[i].strip()[2:].strip()
            req = line.replace('{{ ', '{{').replace(' }}', '}}').split(' ')[0]
            req_rendered = content2[i].strip()[2:].strip().split(' ')[0].strip()
            if len(req_rendered) == 0 or req_rendered not in req:
                req_rendered = req
            if req == 'libgfortran':
                need_f = True
            if req == 'r-base':
                is_r_package = True
            if req_rendered in ['toolchain', 'gcc', 'libgcc', 'libgfortran', 'vc', 'm2w64-toolchain',
                       'mingwpy', 'system', 'gcc-libs', 'm2w64-gcc-libs']:
                messages['Removing {} in favour of compiler()'.format(req)] = True
                change_lines[i] = (lines[i], None)
                need_c = True
                if req in ['m2w64-toolchain', 'mingwpy'] or \
                        (req != req_rendered and req_rendered == 'toolchain'):
                    need_mingw_c = True
                continue
            if req_rendered == 'cython' and not (need_c or need_cxx or need_f):
                messages['Found cython requirement. Adding compiler'] = True
                need_c = True
            if req in ['ninja', 'jom', 'cmake', 'automake', 'autoconf', 'libtool',
                       'make', 'pkg-config', 'automake-wrapper', 'posix', 'm4'] \
                    or req.startswith("{{p") or req.startswith("m2-") \
                    or (req_rendered in ['perl', 'texlive-core', 'curl', 'openssl', 'tar', 'gzip', 'patch']
                        and section == 'build' and req_rendered not in reqs['run']):
                messages['Moving {} from host to build'.format(req)] = True
                build_lines.append(lines[i].rstrip())
                change_lines[i] = (lines[i], None)
                continue
            if req == 'python' and '# [win]' in line:
                messages['Moving `python # [win]` which was used for vc matrix'.format(req)] = True
                change_lines[i] = (lines[i], None)
                python_win_matrix = True
                continue
            if req == 'python':
                python_dep = True

            if req.replace('-', '_') in pinned_packages or \
                    (req_rendered.replace('-', '_') in pinned_packages):
                s = list(filter(None, lines[i].strip().split(' ')))
                if len(s) > 2 and not s[2].startswith('#') and i not in change_lines:
                    if not req.replace('-', '_') in pinned_packages and \
                            not ('m2w64-' + req_rendered.replace('-', '_')) in pinned_packages and \
                            ('# [not win]' not in line and '# [unix]' not in line):
                        msg = 'Not sure how to remove pinnings for {}'.format(req)
                    else:
                        change_lines[i] = (lines[i], lines[i].replace(s[2], ' '*len(s[2])))
                        msg = ('Removing pinnings for {} to use values from '
                               'conda_build_config.yaml. If you need the pin see '
                               '[here](https://conda-forge.org/docs/meta.html#pinning-packages) '
                               'for details.'.format(req))
                    if req == 'numpy':
                        if s[2].startswith('1') or s[2].startswith('x.x'):
                            need_numpy_pin = True
                        if need_numpy_pin and i > reqbuild_section.end:
                            line = lines[i].replace(s[2], ' '*len(s[2]))
                            msg = ('Pinning numpy using pin_compatible. If you need to pin numpy '
                                   'to a specific version see '
                                   '[here](https://conda-forge.org/docs/meta.html'
                                   '#building-against-numpy).')
                            change_lines[i] = (lines[i], line.replace('numpy'+' '*len(s[2]),
                                                "{{ pin_compatible('numpy') }}"))

                    messages[msg] = True


    skip_lines = [(i, line) for i, line in enumerate(lines) if i >= build_section.start and \
                    i <= build_section.end and line.strip().startswith('skip:')]

    if python_win_matrix and not python_dep:
        for i, line in skip_lines:
            skip_line = line.strip()
            skip_line = skip_line[skip_line.find('#'):]

            if len(skip_lines) == 1 and skip_line in [
                '# [win and py36]',
                '# [win and py35]',
                '# [win and py>35]',
                '# [win and py>=36]',
                ]:
                messages["Removed skip for one of py35 or py36 as it's used for vc skipping"] = True
                change_lines[i] = skip_line, None

            if len(skip_lines) == 1 and skip_line in [
                '# [win and py27]',
                '# [win and py2k]',
                '# [win and not py3k]',
                '# [win and py<33]',
                '# [win and py<34]',
                '# [win and py<35]',
                '# [win and not py35]',
                '# [win and not py36]',
                ]:
                messages["Removed skip for py2k and added skip for vc<14"] = True
                change_lines[i] = line, line[:line.find('#')] + '# [win and vc<14]'


    for i, line in enumerate(lines):
        vc14 = 'msvc_compiler: 14.0'
        if line.strip().startswith(vc14):
            need_c = True
            messages["Removed {} and added a skip".format(vc14)] = True
            change_lines[i] = line, line.replace(vc14, 'skip: True  # [win and vc<14]')


    features_section = build_section['features']
    remove_features_section = True

    # Remove vc features
    if features_section is not None:
        for i in range(features_section.start, features_section.end):
            line = lines[i].strip()
            if line.startswith('-'):
                line = line[2:]
                if line.startswith('vc'):
                    messages['Removing vc features'] = True
                    change_lines[i] = (lines[i], None)
                    need_c = True
                elif len(line) > 0:
                    remove_features_section = False

        if remove_features_section:
            messages['Removing features section as it is empty'] = True
            change_lines[features_section.start-1] = (lines[features_section.start-1], None)

    def add_compiler(name, p_name):
        if need_mingw_c:
            build_lines.append(build_space + "{{ compiler('"+ name + "') }}        # [unix]")
            build_lines.append(build_space + "{{ compiler('m2w64_"+ name + "') }}  # [win]")
            messages['Adding ' + p_name + ' compiler with mingw for windows'] = True
        else:
            build_lines.append(build_space + "{{ compiler('"+ name + "') }}")
            messages['Adding ' + p_name + ' compiler'] = True

    if need_f:
        add_compiler('fortran', 'Fortran')
    if need_c:
        add_compiler('c', 'C')
    if need_cxx:
        add_compiler('cxx', 'C++')

    if build_lines:
        build_lines = [' '*(len(reqbuild_line) - len(reqbuild_line.lstrip()))  +'build:'] + build_lines
        pos = requirements_section.start - 1
        change_lines[pos] = lines[pos], lines[pos] + '\n'.join(build_lines)

    if is_r_package:
        messages['Adding merge_build_host: True  # [win]'] = True
        pos = build_section.start - 1
        change_lines[pos] = lines[pos], lines[pos] + ' '*(len(lines[pos + 1]) - len(lines[pos + 1].lstrip()))  + 'merge_build_host: True  # [win]'

    new_lines = []

    for i, line in enumerate(lines):
        if i in change_lines:
            if change_lines[i][1]:
                new_lines.append(change_lines[i][1].rstrip())
        else:
            new_lines.append(line.rstrip())

    new_lines = ('\n'.join(new_lines)).split('\n')

    if python_win_matrix and not python_dep:
        for i, line in enumerate(new_lines):
            l = line.strip()
            ind = l.find('#')
            if ind != -1:
                select = l[ind:]
                for x in ['py27', 'py<33', 'py<34', 'py<35', 'py2k', 'py<=27', 'py==27']:
                    if x in select:
                        new_lines[i] = line.replace(x, 'vc<14')
                        messages['Changed {} in selector {} to vc<14'.format(x, select)] = True
                for x in ['py3k', 'py>27', 'py>=35', 'py>34', 'py>=34', 'py>=33', 'py>33']:
                    if x in select:
                        new_lines[i] = line.replace(x, 'vc==14')
                        messages['Changed {} in selector {} to vc==14'.format(x, select)] = True

    return '\n'.join(new_lines) + '\n', '\n'.join(messages.keys())


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("recipe", help="Path to recipe meta.yaml")
    parser.add_argument("output", help="Path where updated recipe is stored")
    parser.add_argument("config", help="Path to conda_build_config.yaml file")
    args = parser.parse_args()
    new_meta, msg = update_cb3(args.recipe, args.config)
    with io.open(args.output, 'w') as fh:
        fh.write(new_meta)
    print(msg)
