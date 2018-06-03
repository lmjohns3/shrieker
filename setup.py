import os
import setuptools

setuptools.setup(
    name='shrieker',
    version='0.1.1',
    packages=setuptools.find_packages(),
    author='lmjohns3',
    author_email='shrieker@lmjohns3.com',
    description='A pty wrapper for nethack',
    long_description=open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'README.md')).read(),
    license='MIT',
    url='http://github.com/lmjohns3/shrieker',
    keywords='nethack',
    install_requires=['numpy', 'vt102'],
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
