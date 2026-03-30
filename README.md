
# LEGO_DB

A lightweight local database tool for managing LEGO sets.

LEGO_DB allows users to build a local SQLite database from the Rebrickable dataset and manage their owned LEGO sets through a GUI or command-line utilities.

This project is **not affiliated with the LEGO Group**.

Latest release: v1.2.0

![Python](https://img.shields.io/badge/python-3.8+-blue)
![License](https://img.shields.io/badge/license-GPL--3.0-green)

## Features

* Local SQLite database
* Prefix search by set numbers
* Owned set management
* Condition tracking
* Notes per set
* Related sets by the same theme and year
* Copy support with set-number normalization
* Multi-language support
* Export of owned set data to TXT and CSV

## Requirements

* Python 3.8+

## Installation

### 1. Download dataset

Download the required CSV files from Rebrickable:

https://rebrickable.com/downloads/

Required files:

* themes.csv
* sets.csv

Place them in the following directory:

```
src/
└ lego_db/
  └ data/
    └ csv/
```

### 2. Build database

```
python scripts/makeLegoDB.py
```

### 3. Run application

You can start the GUI by double-clicking:

```
legoDB.pyw
```

Or run it from the command line:

```
python legoDB.pyw
```

On first run:

* A language selection window appears
* The selected language is saved in `config.json`

### Optional: install as a package

```
pip install -e .
```

This makes the package importable as `lego_db` and allows module-style execution such as:

```
python -m lego_db
```

## Basic Usage

### Search by set number prefix

Type a set-number prefix in the search box:

```
123
```

This matches set numbers such as:

```
123-1
1230-1
...
```

### View owned sets

```
owned
```

Filter owned sets by condition:

```
owned 0
owned 1
owned 2
```

### Quick focus shortcut

* Press `/`

## Commands

Commands are entered directly in the search box.

| Command            | Meaning                           |
| ------------------ | --------------------------------- |
| `+0000-1`        | add to owned                      |
| `-0000-1`        | remove from owned                 |
| `2>0000-1`       | set condition to 2                |
| `[note]>0000-1`  | add a note                        |
| `2[note]>0000-1` | set condition to 2 and add a note |
| `[note]2>0000-1` | set condition to 2 and add a note |

Multiple commands can be combined in a single input:

```
+1234-1 -5678-1 2[gift]>1111-1
```

Invalid tokens are ignored.

In the result list, you can use right-click for quick actions:

* Add the selected set to owned
* Remove the selected set from owned

## Notes

Notes are written inside square brackets:

```
[Note]>1111-1
```

Examples:

```
[2026. 01. 01. Gift]>1111-1
[!@#$%^&*()]>1111-1
```

### Escaping special characters

You can include `]` or `\` in notes by escaping them:

```
[]]>1234-1 → ]
[\]>1234-1 → \
[a]b]>1234-1 → a]b
[a\b]>1234-1 → a\b
```

Control characters such as newline are not allowed in notes.

## Set details

Each set can show:

* Full set information
* Theme hierarchy
* Piece count
* Release year
* Owned status
* Condition
* Notes

The copy feature supports normalization (for example, `1234-1 → 1234`).

### Condition values

* `0` — default (light blue)
* `1` — bad (light pink)
* `2` — good (light green)

### Related sets

When you select a set, related sets from the same theme and year are shown automatically.

### Clipboard

Two copy modes are available:

* Quick copy button
* Copy from the detail window, with optional normalization

Example output:

```
<parent_theme> <theme> <set_num> <name>, <pieces>pc, <year>
```

### Export owned data

The exporter creates both files in the project directory:

* `owned_export.txt`
* `owned_export.csv`

Run:

```
python scripts/owned_data_exporter.py
```

### Import owned data

You can restore owned set data from a TXT export.

Run:

```
python scripts/owned_data_importer.py
```

## Data

* CSV data is **not included** in the repository
* Users must download dataset files manually from Rebrickable
* Redistribution of the dataset may violate Rebrickable's terms of use

## Disclaimer

* LEGO® is a trademark of the LEGO Group
* This project is not affiliated with the LEGO Group
* Data is provided by Rebrickable and is not redistributed here

## AI Usage Disclosure

Some parts of this project were developed with assistance from ChatGPT (OpenAI):

* Code drafting
* Refactoring and structure improvements
* Translations

All final decisions and modifications were reviewed by the author.

## License

This project is licensed under the terms of the GPL-3.0 License.

See the [LICENSE](./LICENSE) ([ko-KR](https://www.olis.or.kr/license/Detailselect.do?lId=1072)) file for details.
