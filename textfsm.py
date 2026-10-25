import sys
import importlib.util

_sp_list = [p for p in sys.path if 'site-packages' in p]
if _sp_list:
    _sp = _sp_list[0]
    _tf_init = f'{_sp}/textfsm/__init__.py'
    _spec = importlib.util.spec_from_file_location('textfsm', _tf_init, submodule_search_locations=[f'{_sp}/textfsm'])
    if _spec:
        _mod = importlib.util.module_from_spec(_spec)
        sys.modules['textfsm'] = _mod
        _spec.loader.exec_module(_mod)
        for _k in list(_mod.__dict__.keys()):
            if not _k.startswith('__'):
                globals()[_k] = getattr(_mod, _k)
        __path__ = _mod.__path__

if __name__ == '__main__':
    from textfsmlab import main
    main()
