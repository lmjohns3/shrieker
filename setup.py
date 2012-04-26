import setuptools

setuptools.setup(
    name='lmj.nethack',
    version='0.1',
    namespace_packages=['lmj'],
    packages=setuptools.find_packages(),
    author='Leif Johnson',
    author_email='leif@leifjohnson.net',
    description='A pty wrapper over nethack',
    long_description=open('README.md').read(),
    license='MIT',
    keywords=('nethack '
              ),
    url='http://github.com/lmjohns3/py-nethack',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Topic :: Games/Entertainment',
        'Topic :: Scientific/Engineering :: Artificial Intelligence',
        ],
    )
