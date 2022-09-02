# rs-janssen is available under the MIT License. https://github.com/roundservices/rs-midpoint/
# Copyright (c) 2022, Round Services LLC - https://roundservices.biz/
#
# Author: Gustavo J Gallardo - ggallard@roundservices.biz
#

from setuptools import setup

setup(
    name='rs-janssen',
    version='1.0.0',
    description='Python utilities for Janssen',
    url='git@github.com:RoundServices/rs-janssen.git',
    author='Round Services',
    author_email='ggallard@roundservices.biz',
    license='MIT License',
    install_requires=['rs-utils'],
    packages=['rs.janssen'],
    zip_safe=False,
    python_requires='>=3.0'
)
