from marge.app import main


def run():
    try:
        main()
    except Exception as err:
        print('Exception occured')
        if hasattr(err, 'stdout'):
            # pylint: disable=no-member
            print(f'stdout was: {err.stdout}')
        if hasattr(err, 'stderr'):
            # pylint: disable=no-member
            print(f'stderr was: {err.stderr}')
        raise


if __name__ == '__main__':
    run()
