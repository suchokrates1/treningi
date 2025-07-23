#!/usr/bin/env python
"""Generate a werkzeug password hash from the provided password."""
from werkzeug.security import generate_password_hash
import sys

if len(sys.argv) != 2:
    print("Usage: python generate_password_hash.py <password>")
    sys.exit(1)

print(generate_password_hash(sys.argv[1]))
