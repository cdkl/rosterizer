# rosterizer

A simple tool for building curling teams based on data exported from Curling Club Manager. Intended features include attempting to balance player position requests and "plays with" requests against data regarding skill level and even past performance.

# Configuration

rosterizer needs a database connection defined in `my.cnf`, which can be created by copying `my.cnf.default` and providing the connection details within. You will need a user defined that has permission to access database `rosterizer` (you may also need to create this database) and the user will also need permissions to create other databases in order for unit tests to work.

# Venv and required packages

It's helpful to set up your venv

`python -m venv venv`

`./venv/scripts/activate`

You will also need these packages. (todo: add a requirements file)

`pip install django mysqlclient beautifulsoup4 lxml pytest-django`

# Input file format

See the file `test_data/TestImport1.html` for a sample of the file output that Curling Club Manager outputs.

# Testing

```pytest```


