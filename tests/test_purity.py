"""Console operations must fail the same purity gate as other cell I/O."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from standard.conformance import run
from tools.polycell import package
from tools.polycell.purity import has_forbidden_io


BAD = {
    'python': ['\nprint("debug")\n',
               '\nimport logging\nlogging.info("debug")\n',
               '\nimport sys as system\nsystem.stderr.write("debug")\n',
               '\nfrom builtins import print as emit\nemit("debug")\n',
               '\nfrom sys import stdout as stream\nstream.writelines(["debug"])\n'],
    'ts': ['\nconsole.log("debug");\n',
           '\nconsole?.error?.("debug");\n',
           '\nconsole["warn"]("debug");\n',
           '\nprocess.stderr.write("debug");\n',
           '\nconst fixture = `value ${console.debug("debug")}`;\n'],
    'rust': ['\nfn fixture() { println!("debug"); }\n',
             '\nfn fixture() { std::eprintln!("debug"); }\n',
             '\nfn fixture() { print!["debug"]; }\n',
             '\nfn fixture() { dbg!(7); }\n',
             '\nfn fixture() { log::info!("debug"); }\n'],
}

DATA = {
    'python': '\nFIXTURE = "print(1); logging.info(1); sys.stderr.write(1)"\n# print("debug")\n',
    'ts': '\nconst fixtureText = "console.log(1)";\n'
          'const fixtureRegex = /console.log(value)/;\n'
          'const fixtureTemplate = `console.warn(${1})`;\n/* console.error("debug"); */\n',
    'rust': '\nconst FIXTURE: &str = r###"println!(1); eprintln!(2); dbg!(3)"###;\n'
            '/* outer /* nested */ println!("debug"); */\n'
            'fn fixture<\'a>(value: &\'a str) -> String { format!("eprintln! {:?}", value) }\n',
}


class ConsolePurityGateTests(unittest.TestCase):
    def check_language(self, selector):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            base=root/'base'
            manifest=package.export(selector,base)
            language=manifest['owner']
            source=(base/manifest['implementation']).read_text()
            app=root/'app'
            package.assemble([base],app,generate=True)
            cell=app/'cells'/language/(selector.replace('.','_')+'.'+package.EXT[language])
            for number, addition in enumerate(BAD[language]):
                proposed=source+addition
                cell.write_text(proposed)
                with self.subTest(language=language, case=number, gate='conformance'):
                    self.assertTrue(any(f['code']=='PC008' and f['severity']=='error' for f in run(app)))
                with self.subTest(language=language, case=number, gate='package'):
                    with self.assertRaisesRegex(ValueError,'I/O'):
                        package.replace(base,proposed,root/f'bad-{number}')
                forged=root/f'forged-{number}'
                package.snapshot(base,forged)
                (forged/manifest['implementation']).write_text(proposed)
                changed={**manifest,'files':{**manifest['files'],manifest['implementation']:package.digest(proposed.encode())}}
                (forged/'package.json').write_bytes(package.json_bytes(changed))
                with self.subTest(language=language, case=number, gate='verify'):
                    with self.assertRaisesRegex(ValueError,'I/O'):
                        package.verify(forged)
                with self.subTest(language=language, case=number, gate='qualification-preflight'), \
                     patch.object(package,'_qualify_snapshot') as evaluate:
                    with self.assertRaisesRegex(ValueError,'I/O'):
                        package.qualify(forged,base,'unused-image')
                    evaluate.assert_not_called()
            neutral=source+DATA[language]
            cell.write_text(neutral)
            self.assertFalse(any(f['code']=='PC008' for f in run(app)))
            package.replace(base,neutral,root/'neutral')
            package.verify(root/'neutral')

    def test_python_console_purity_in_both_gates(self):
        self.check_language('shipping.cost')

    def test_typescript_console_purity_in_both_gates(self):
        self.check_language('notify.render')

    def test_rust_console_purity_in_both_gates(self):
        self.check_language('pricing.quote')


class ConsoleSyntaxTests(unittest.TestCase):
    def test_python_ast_distinguishes_logging_from_data_and_methods(self):
        for source in ('print\n(1)', 'import builtins as b\nb.print(1)',
                       'import sys\nsys.stdout.buffer.write(b"x")',
                       'from logging import getLogger\nlogger=getLogger()'):
            with self.subTest(source=source):
                # A bare name followed by a separate expression is not a call.
                self.assertEqual(source != 'print\n(1)', has_forbidden_io('py',source))
        for source in ('value = "print(1)"\n# logging.info(1)',
                       'result = input_data["print"]', 'result = formatter.print("pure")'):
            with self.subTest(source=source):
                self.assertFalse(has_forbidden_io('py',source))

    def test_typescript_templates_optional_calls_and_regex_literals(self):
        for source in ('console /* gap */ . log(1)', 'console!["log"](1)',
                       'const value = `outer ${`inner ${console.error(1)}`}`',
                       'const value = `outer ${{value: console.warn(1)}}`',
                       'const value = total / console.log(1)', 'const log = console.log'):
            with self.subTest(source=source):
                self.assertTrue(has_forbidden_io('ts',source))
        for source in ('const pattern = /console.log(value)/',
                       r'const pattern = /[\/]console.log(value)/',
                       'const value = `console.log(${input.value})`',
                       'const value = `console.log(${`nested text`})`',
                       'const data = {console: "log(1)"};',
                       'const value = input.console.log; // domain data'):
            with self.subTest(source=source):
                self.assertFalse(has_forbidden_io('ts',source))

    def test_rust_macros_raw_strings_comments_and_lifetimes(self):
        for source in ('std::println! {"x"}', 'eprint!["x"]',
                       'format!("{}", dbg!(value))', 'tracing::info!("x")',
                       "fn f<'a>(v: &'a str) { eprintln!(\"{}\", v); }"):
            with self.subTest(source=source):
                self.assertTrue(has_forbidden_io('rs',source))
        for source in ('let text = br###"eprintln!(1)"###;',
                       '/* nested /* comment */ println!(1); */',
                       "fn f<'a>(v: &'a str) -> String { format!(\"{}\", v) }",
                       "let value = 'a'; let text = r\"dbg!(1)\";"):
            with self.subTest(source=source):
                self.assertFalse(has_forbidden_io('rs',source))

    def test_existing_transport_and_file_patterns_remain_enforced(self):
        for extension,source in (('py','import socket'),('py','open("file")'),
                                 ('ts','fetch("url")'),('ts','import fs from "node:fs"'),
                                 ('rs','use std::fs;'),('rs','tokio::net::TcpStream')):
            with self.subTest(extension=extension,source=source):
                self.assertTrue(has_forbidden_io(extension,source))


if __name__=='__main__':
    unittest.main()
