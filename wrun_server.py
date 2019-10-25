import sys

import wrun


def main(action, *args):
    if action == 'install':
        from wrun.win32_service import WinService
        WinService.install(wrun.Service, *args)
    elif action == 'run':
        s = wrun.Service(*args)
        s.run()
    else:
        assert False


if __name__ == '__main__':
    main(*sys.argv[1:])
