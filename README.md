# LEGO_DB

<p align="center">
  <img src="https://github.com/user-attachments/assets/e18d5154-d7e4-4e9e-87e6-845ff3e10b3f" width="800">
</p>

<p align="center">
A lightweight local database tool for managing LEGO sets.
</p>

---

**LEGO_DB** is a lightweight Python application that builds a **local SQLite database** from the Rebrickable dataset and allows users to manage their **owned LEGO sets** through a GUI or command-line style input.

This project is **not affiliated with the LEGO Group**.

![Python](https://img.shields.io/badge/python-3.8+-blue)
![License](https://img.shields.io/badge/license-GPL--3.0-green)
![GitHub release](https://img.shields.io/github/v/release/sternenlicht02/LEGO_DB)

## Features

* Local SQLite database
* Prefix search by set numbers
* Owned set management
* Condition tracking
* Notes per set
* Related sets (same theme and year)
* Clipboard copy with set-number normalization
* Multi-language support
* Export owned data to TXT and CSV

## Requirements

* Python **3.8+**

## Installation

### 1. Download dataset

Download the required CSV files from Rebrickable:

https://rebrickable.com/downloads/

Required files:

```
themes.csv
sets.csv
```

Place them in:

```
src/
└─ lego_db/
   └─ data/
      └─ csv/
         ├─ themes.csv
         └─ sets.csv
```

### 2. Build the database

Run the database generation script:

```
python scripts/makeLegoDB.py
```

This creates the local SQLite database from the CSV files.

### 3. Run the application

Start the GUI:

```
python legoDB.pyw
```

or simply double-click:

```
legoDB.pyw
```

On the first run:

* A language selection window appears
* The selected language is saved to `config.json`

### Optional: install as a package

You can install the project in editable mode:

```
pip install -e .
```

This allows module-style execution:

```
python -m lego_db
```

## Basic Usage

### Search by set number prefix

Enter a prefix in the search box:

```
123
```

This matches:

```
123-1
1230-1
...
```

### View owned sets

```
owned
```

Filter by condition:

```
owned 0
owned 1
owned 2
```

### Quick focus shortcut

Press:

```
/
```

to focus the search box.

## Commands

Commands are entered directly into the search box.

| Command            | Meaning                           |
| ------------------ | --------------------------------- |
| `+0000-1`          | Add set to owned                  |
| `-0000-1`          | Remove set from owned             |
| `2>0000-1`         | Set condition to 2                |
| `[note]>0000-1`    | Add note                          |
| `2[note]>0000-1`   | Set condition and add note        |
| `[note]2>0000-1`   | Same as above                     |

Multiple commands can be combined:

```
+1234-1 -5678-1 2[gift]>1111-1
```

Invalid tokens are ignored.

### Context menu actions

In the result list you can **right-click** to:

* Add selected set to owned
* Remove selected set from owned

## Notes

Notes are written inside square brackets.

Example:

```
[Note]>1111-1
```

Example notes:

```
[2026. 01. 01. Gift]>1111-1
[!@#$%^&*()]>1111-1
```

### Escaping special characters

You can escape `]` or `\` using `\`.

```
[]]>1234-1 → ]
[\]>1234-1 → \
[a]b]>1234-1 → a]b
[a\b]>1234-1 → a\b
```

Control characters such as newline are not allowed.

## Set details

Each set displays:

* Full set information
* Theme hierarchy
* Piece count
* Release year
* Owned status
* Condition
* Notes

### Condition values

| Value        | Meaning      | Color        |
| ------------ | ------------ | ------------ |
| `0`          | Default      | Light Blue   |
| `1`          | Bad          | Light Pink   |
| `2`          | Good         | Light Green  |

### Related sets

When a set is selected, related sets from the **same theme and year** are automatically shown.

## Clipboard

Two copy modes are available:

* Quick copy button
* Copy from the detail window

Optional **set-number normalization** is supported.

Example output:

```
<parent_theme> <theme> <set_num> <name>, <pieces>pc, <year>
```

## Export owned data

Export owned sets:

```
python scripts/owned_data_exporter.py
```

Generated files:

```
owned_export.txt
owned_export.csv
```

## Import owned data

Restore owned set data from a TXT export:

```
python scripts/owned_data_importer.py
```

## Data

* CSV data is **not included** in the repository
* Users must download datasets manually from Rebrickable
* Redistributing the dataset may violate Rebrickable's terms of use

## Disclaimer

* **LEGO®** is a trademark of the LEGO Group
* This project is **not affiliated with the LEGO Group**
* Data is provided by **Rebrickable** and is not redistributed here

## AI Usage Disclosure

Some parts of this project were developed with assistance from **ChatGPT (OpenAI)**:

* Code drafting
* Refactoring
* Structure improvements
* Translation assistance

All final decisions and modifications were reviewed by the project author.

## License

This project is licensed under the **GPL-3.0 License**.

See the [LICENSE](./LICENSE) ([ko-KR](https://www.olis.or.kr/license/Detailselect.do?lId=1072)) file for details.
