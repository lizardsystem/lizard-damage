from setuptools import setup

version = '2.0.4'

long_description = '\n\n'.join([
    open('README.rst').read(),
    open('CREDITS.rst').read(),
    open('CHANGES.rst').read(),
    ])

install_requires = [
    'Django >= 1.4, < 1.7',
    'django-extensions',
    'django-nose',
    'lizard-task >= 0.16',
    'lizard-map >= 4.40, < 5.0',
    'lizard-ui >= 4.40, < 5.0',
    'lizard-damage-calculation',
    'xlrd',
    'Pillow',
    'pyproj',
    'mock',
    'factory-boy',
    'django-appconf'
    ],

tests_require = [
    ]

setup(name='lizard-damage',
      version=version,
      description="Schade Module: berekent schade aan de hand van gebeurtenissen",
      long_description=long_description,
      # Get strings from http://www.python.org/pypi?%3Aaction=list_classifiers
      classifiers=['Programming Language :: Python',
                   'Framework :: Django',
                   ],
      keywords=[],
      author='Arjan Verkerk',
      author_email='arjan.verkerk@nelen-schuurmans.nl',
      url='',
      license='GPL',
      packages=['lizard_damage'],
      include_package_data=True,
      zip_safe=False,
      install_requires=install_requires,
      tests_require=tests_require,
      extras_require = {'test': tests_require},
      entry_points={
          'console_scripts': [
          ]},
      )
