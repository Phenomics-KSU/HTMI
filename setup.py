from setuptools import setup

def readme():
    with open('README.rst') as f:
        return f.read()

if __name__ == "__main__":
    setup(name='HTMI',
          version='1.0',
          description='High Throughput Mapping and Identification',
          long_description=readme(),
          keywords='mapping identification htp phenotyping',
          url='TODO',
          author='',
          author_email='',
          license='TODO',
          packages=['src'],
          install_requires=[],
          zip_safe=False)