"""Shared static checks for known cell I/O and console/logging APIs."""
from __future__ import annotations

import ast
import re


# Retain the established transport/file patterns; both admission paths use them.
IMPURE = {
    "py": re.compile(r"^\s*(import|from)\s+(socket|subprocess|requests|httpx|urllib|psycopg|sqlite3|grpc)\b|os\.system|open\(", re.M),
    "ts": re.compile(r"from\s+\"node:(fs|net|http|child_process)\"|\bfetch\(|require\(", re.M),
    "rs": re.compile(r"std::(net|fs|process)|reqwest|tokio::net", re.M),
}


def _dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute) and (base := _dotted(node.value)):
        return base + "." + node.attr
    return None


def _python_console(source):
    try:
        tree = ast.parse(source)
    except (SyntaxError, RecursionError):
        return False  # Syntax/compilation is checked by executable qualification.
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                if name.name.split(".")[0] == "logging":
                    return True
                aliases[name.asname or name.name.split(".")[0]] = name.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] == "logging":
                return True
            for name in node.names:
                aliases[name.asname or name.name] = node.module + "." + name.name
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not (name := _dotted(node.func)):
            continue
        first, *rest = name.split(".")
        name = ".".join([aliases.get(first, first), *rest])
        if name in {"print", "builtins.print", "__builtins__.print"}:
            return True
        streams = ("sys.stdout.", "sys.stderr.", "sys.__stdout__.", "sys.__stderr__.")
        if name.startswith(streams) and name.rsplit(".", 1)[-1] in {"write", "writelines", "flush"}:
            return True
    return False


_RAW_RUST = re.compile(r'(?:br|r)(#*)"')
_RUST_CHAR = re.compile(r"'(?:\\(?:u\{[0-9a-fA-F_]+\}|x[0-9a-fA-F]{2}|.)|[^\\'\n])'")
_REGEX_PRECEDERS = {"(", "[", "{", "=", ":", ",", ";", "!", "?", "&&", "||", "??", "=>",
                     "+", "-", "*", "/", "%", "~", "return", "case", "throw", "typeof", "void"}
_LITERAL = "\0literal"


def _quoted_end(source, start, quote):
    i = start + 1
    while i < len(source):
        if source[i] == "\\":
            i += 2
        elif source[i] == quote:
            return i + 1
        else:
            i += 1
    return i


def _regex_end(source, start):
    i, in_class = start + 1, False
    while i < len(source) and source[i] not in "\r\n":
        char = source[i]
        if char == "\\":
            i += 2
            continue
        if char == "[":
            in_class = True
        elif char == "]":
            in_class = False
        elif char == "/" and not in_class:
            i += 1
            while i < len(source) and source[i].isalpha():
                i += 1
            return i
        i += 1
    return None


def _lexemes(source, extension):
    """Skip literal/comment text; retain executable TS template expressions.

    Frames are iterative so nested templates do not consume the Python stack.
    Rust character literals are distinct from lifetime annotations.
    """
    result, frames, i = [], [None], 0
    while i < len(source):
        char = source[i]
        if frames[-1] == "template":
            if char == "\\":
                i += 2
            elif char == "`":
                frames.pop()
                result.append(_LITERAL)
                i += 1
            elif source.startswith("${", i):
                frames.append(0)
                result.append("(")
                i += 2
            else:
                i += 1
            continue
        if char.isspace():
            i += 1
            continue
        if source.startswith("//", i):
            end = source.find("\n", i + 2)
            i = len(source) if end < 0 else end
            continue
        if source.startswith("/*", i):
            depth, i = 1, i + 2
            while i < len(source) and depth:
                if source.startswith("/*", i):
                    depth, i = depth + 1, i + 2
                elif source.startswith("*/", i):
                    depth, i = depth - 1, i + 2
                else:
                    i += 1
            continue
        if extension == "rs" and (raw := _RAW_RUST.match(source, i)):
            closing = '"' + raw[1]
            end = source.find(closing, raw.end())
            i = len(source) if end < 0 else end + len(closing)
            result.append(_LITERAL)
            continue
        if char == '"' or (extension == "ts" and char == "'"):
            i = _quoted_end(source, i, char)
            result.append(_LITERAL)
            continue
        if extension == "rs" and char == "'" and (literal := _RUST_CHAR.match(source, i)):
            i = literal.end()
            result.append(_LITERAL)
            continue
        if extension == "ts" and char == "`":
            frames.append("template")
            result.append(_LITERAL)
            i += 1
            continue
        if extension == "ts" and char == "/" and (not result or result[-1] in _REGEX_PRECEDERS):
            if (end := _regex_end(source, i)) is not None:
                i = end
                result.append(_LITERAL)
                continue
        if isinstance(frames[-1], int):
            if char == "}" and frames[-1] == 0:
                frames.pop()
                result.append(")")
                i += 1
                continue
            if char in "{}":
                frames[-1] += 1 if char == "{" else -1
        if char.isalpha() or char in "_$":
            end = i + 1
            while end < len(source) and (source[end].isalnum() or source[end] in "_$"):
                end += 1
            result.append(source[i:end])
            i = end
            continue
        operator = source[i:i + 2]
        if operator in {"?.", "::", "=>", "&&", "||", "??"}:
            result.append(operator)
            i += 2
        else:
            result.append(char)
            i += 1
    return result


_CONSOLE_METHODS = {"log", "info", "debug", "warn", "error", "trace", "assert", "dir", "dirxml", "table",
                    "clear", "count", "countReset", "group", "groupCollapsed", "groupEnd", "time", "timeEnd",
                    "timeLog", "timeStamp", "profile", "profileEnd"}


def has_forbidden_io(extension: str, source: str) -> bool:
    if IMPURE[extension].search(source):
        return True
    if extension == "py":
        return _python_console(source)
    pieces = _lexemes(source, extension)
    for i, piece in enumerate(pieces):
        tail = pieces[i + 1: i + 7]
        if extension == "rs":
            if piece in {"print", "println", "eprint", "eprintln", "dbg"} and tail[:1] == ["!"]:
                return True
            if piece in {"log", "tracing"} and tail[:1] == ["::"]:
                return True
        elif i == 0 or pieces[i - 1] not in {".", "?."}:
            if piece == "process" and len(tail) >= 4 and tail[0] in {".", "?."} and tail[1] in {"stdout", "stderr"} and tail[2] in {".", "?."} and tail[3] == "write":
                return True
            if piece != "console":
                continue
            j = i + 1
            if j < len(pieces) and pieces[j] == "!":
                j += 1
            if j < len(pieces) and pieces[j] in {".", "?."}:
                j += 1
                if j < len(pieces) and pieces[j] in _CONSOLE_METHODS:
                    return True
            if j < len(pieces) and pieces[j] == "[":
                depth = 1
                j += 1
                while j < len(pieces) and depth:
                    depth += (pieces[j] == "[") - (pieces[j] == "]")
                    j += 1
                if j < len(pieces) and pieces[j] == "?.":
                    j += 1
                if j < len(pieces) and pieces[j] == "(":
                    return True
    return False
