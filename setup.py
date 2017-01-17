from setuptools import setup


setup(
   name='wrun',
   version='0.1.4',
   description='Run Remote Windows Executables',
   license="MIT",
   author='Marco De Paoli',
   author_email='depaolim@gmail.com',
   url="https://github.com/depaolim/wrun",
   packages=['wrun'],
   install_requires=[], # external packages as dependencies
   scripts=['wrun_service.py']
)
