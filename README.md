# trask [![Build Status](https://travis-ci.org/nicholasbishop/trask.svg?branch=master)](https://travis-ci.org/nicholasbishop/trask)

Declarative recipe-based task runner

Usage:

    python3 -m trask [--dry-run] <path>

- [Schema](trask/schema)
- [Emacs mode](trask.el)

## Example

```
docker-build {
  tag 'proj1'
  from 'amazonlinux:2'
  recipes {
    yum-install {
      pkg [ 'gcc' 'openssl-devel' ]
    }
    install-rust {
      channel 'nightly'
    }
  }
  workdir '/app'
}

docker-run {
  image 'proj1'
  init true
  volumes [
    {
      host '..'
      container '/app'
    }
  ]
  commands [
    'cargo build --release'
    'cargo test --release'
  ]
}

create-temp-dir {
  var 'install-dir'
}

copy {
  recipe 'copy'
  src [
    proj1.service'
    '../target/release/proj1'
  ]
  dst install-dir
}

set {
  user 'nbishop'
  host '12.34.56.78'
  identity env('SSH_KEY_PATH')
}

upload {
  replace true
  identity identity
  user user
  host host
  src install-dir
  dst 'app'
}

ssh {
  identity identity
  user user
  host host
  commands [
    'sudo cp app/proj1.service /etc/systemd/system/'
    'sudo systemctl enable proj1'
    'sudo systemctl restart proj1'
  ]
}
```
