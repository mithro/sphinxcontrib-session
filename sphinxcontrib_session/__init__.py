#!/usr/bin/python
# coding: utf-8

import re

import os
from shutil import copyfile

from docutils import nodes
from docutils.parsers import rst

from sphinx.errors import ExtensionError
from sphinx.directives.code import CodeBlock

import pygments
from pygments.token import Token
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import HtmlFormatter


class SessionDirective(CodeBlock):

    def run(self):
        n = session()
        n.contains = CodeBlock.run(self)
        return [n]


class session(nodes.Element): pass


def token_is_whitespace(token):
    token_type, token_text = token
    if token_type is not Token.Text:
        return False
    return not token_text.strip()


span_re = re.compile('^(<span[^>]*)>(.*?)</span>(.*?)$', re.DOTALL)


def to_data_content(token, i):
    if not i.strip():
        return i

    m = span_re.match(i)
    assert m, repr(i)

    # FIXME: Why is this needed...
    # Append an extra newline if needed.
    token_type, token_text = token
    if token_text.endswith('\n'):
        extra = '\n'
    else:
        extra = ''

    return '{} data-content="{}"></span>'.format(m.group(1), m.group(2)+extra+m.group(3))


def fix_token_newline(token, i):
    # FIXME: Why is this needed?
    token_type, token_text = token
    if not token_text.endswith('\n') and i.endswith('\n'):
        i = i[:-1]
    return i


SESSION_TYPES = {
    'BashLexer':        'shell-session',
    'BatchLexer':       'doscon',
    'PowerShellLexer':  'ps1con',
    'TcshLexer':        'tcshcon',
    'Python2Lexer':     'pycon',
    'PythonLexer':      'pycon',
    'RdLexer':          'rconsole',
    'SLexer':           'rconsole',
    'PostgresLexer':    'psql',
    'RubyLexer':        'rbconn',
}

def session_lexer(lexer):
    lexer_name = lexer.__class__.__name__

    if 'Session' in lexer_name:
        return lexer
    if 'Console' in lexer_name:
        return lexer

    if lexer_name in SESSION_TYPES:
        return get_lexer_by_name(SESSION_TYPES[lexer_name])
    else:
        print(lexer, lexer_name, "not found in SESSION_TYPES")

    return None


def visit_session_html(self, node):
    formatter = self.highlighter.get_formatter(nowrap=True)

    if not hasattr(node, 'contains'):
        print("Warning no contents found on", node)
        return

    data_node = node.contains[0]

    content = data_node.rawsource

    lang = data_node.get('language', 'auto')
    if lang in ('auto', 'default'):
        lexer_orig = guess_lexer(content)
    else:
        lexer_orig = get_lexer_by_name(lang)

    lexer = session_lexer(lexer_orig)
    if lexer is None:
        print("""\
Session contents should be a XXXSession lexer like `console`, `doscon` or \
`ps1con`. Got instead '{}'.""".format(lexer_orig))
        return

    lang = data_node.get('language', 'default')
    linenos = data_node.get('linenos', False)
    highlight_args = data_node.get('highlight_args', {})

    output = []
    output.append(self.starttag(
        node, 'div', suffix='', CLASS='highlight-%s notranslate' % lang))
    output.append(self.starttag(node, 'div', suffix='', CLASS='highlight'))
    output.append(self.starttag(node, 'pre'))

    tokens = list(pygments.lex(content, lexer))

    token_groups = [[tokens.pop(0),]]
    for token in tokens:
        current_group = token_groups[-1]

        # Is this just a whitespace token?
        if token_is_whitespace(token) and current_group[-1][0] is Token.Generic.Prompt:
            current_group.append(token)
        else:
            token_groups.append([token])

    while len(token_groups) > 0:
        current_tokens = token_groups.pop(0)

        o = pygments.format(current_tokens, formatter)
        i = fix_token_newline(current_tokens[-1], o)

        if current_tokens[0][0] in (Token.Generic.Prompt, Token.Generic.Output):
            i = to_data_content(current_tokens[-1], i)

        #print(current_tokens, '\n', repr(o), '\n', repr(i), '\n')
        output.append(i)

    output.append('</pre>')
    output.append('</div>')
    output.append('</div>')
    self.body.append("".join(output))
    raise nodes.SkipNode


def depart_session_html(self, node):
    return


def _is_html(app):
    return app.builder.name in ('html', 'readthedocs')


def add_stylesheet(app):
    app.add_stylesheet('session.css')


def copy_stylesheet(app, exception):
    if not _is_html(app) or exception:
        return

    source = os.path.abspath(os.path.dirname(__file__))
    dest = os.path.join(app.builder.outdir, '_static', 'session.css')
    copyfile(os.path.join(source, "session.css"), dest)


def setup(app):
    app.connect('builder-inited', add_stylesheet)
    app.connect('build-finished', copy_stylesheet)
    app.add_directive('session', SessionDirective)
    app.add_node(session, html=(visit_session_html, depart_session_html))
