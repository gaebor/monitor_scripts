#!/usr/bin/env bash
source="$1"
target="$2"
mv "$source" "$target"
ln -s "$target/`basename "$source"`" "$source"
