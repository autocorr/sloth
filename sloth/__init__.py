from pathlib import Path
from configparser import ConfigParser


system_path = [
    Path('sloth.config').absolute(),
    Path('~/.sloth.config'),
    Path('~/.sloth/config'),
    Path('~/.config/sloth/config'),
    Path(__file__).parent/Path('default_config'),
]
system_path = [p.expanduser() for p in system_path]

CONFIG = ConfigParser()
for filen in system_path:
    result = CONFIG.read(filen)
    if result:
        CONFIG.set('Paths', 'config_file', value=str(filen))
        break
else:
    raise FileNotFoundError('Could not find configuration file.')


