#!/usr/bin/env bash
# printf %b interprets backslash escapes; %s does not.

printf '%b\n' 'a\tb\nc'
printf '%s\n' 'a\tb\nc'
printf '%b %b\n' 'x\ty' 'p\nq'
