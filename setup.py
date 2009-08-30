from distutils.core import setup

from eggy import __version__, email, website

def main():
    setup(
        name='eggy',
        version=__version__,
        license='GPL3',
        author='Mark Florisson',
        author_email=email,
        url=website,
        description=('An IDE/editor for several programming languages, '
                     'including Python, Java, C, Perl and others'),

        packages=['eggy', 'eggy.chardet', 'eggy.decorators', 'eggy.gui', 
                  'eggy.model', 'eggy.compile', 'eggy.network', 
                  'eggy.plugins', 'eggy.project', 'eggy.shell'],

        package_data={'eggy': ['img/*.ico', 'img/*.png', 'img/readme', 
                               'img/eggy/*']},
        scripts=['bin/eggy'])

if __name__ == '__main__':
    main()
