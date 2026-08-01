import sys
from typing import Any


def __getattr__(name: str) -> Any:
    module_dict = sys.modules[__name__].__dict__
    neither_module_imported = 'direct' not in module_dict and 'flask' not in module_dict

    if name == 'direct':
        if neither_module_imported:
            from . import direct

            module_dict['direct'] = direct
        elif 'flask' in module_dict:
            raise AttributeError('Only one of `direct` and `flask` can be used!')
        return module_dict['direct']

    elif name == 'flask':
        if neither_module_imported:
            from . import flask

            module_dict['flask'] = flask
        elif 'direct' in module_dict:
            raise AttributeError('Only one of `direct` and `flask` can be used!')
        return module_dict['flask']

    elif name in module_dict:
        return module_dict[name]

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
