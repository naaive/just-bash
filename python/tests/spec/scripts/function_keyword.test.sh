#!/usr/bin/env bash
# All three function-definition forms.

# function NAME { ... }
function alpha {
  echo "alpha:$1"
}

# function NAME() { ... }
function beta() {
  echo "beta:$1"
}

# NAME() { ... }
gamma() {
  echo "gamma:$1"
}

alpha 1
beta 2
gamma 3
