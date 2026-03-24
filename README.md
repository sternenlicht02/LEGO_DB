# LEGO DB

A local SQLite + GUI application for browsing and managing LEGO sets using Rebrickable data.

This project is **not affiliated with the LEGO Group**.

## Features

- Local SQLite database
- Prefix search by set number
- Owned set management
- Condition tracking (0 / 1 / 2)
- Per-set notes
- Related sets (same theme & year)
- Multi-language support (English / 한국어)

## Requirements

- Python 3.8+

## Installation

### 1. Download dataset

Download CSV files from:

```
https://rebrickable.com/downloads/
```

Required files:

- themes.csv
- sets.csv

Place them in:

```
csv/
```

### 2. Build database

```
python makeLegoDB.py
```

### 3. Run application

```
python legoDB.py
```

## Usage

### Basic search

```
123
```

Performs prefix matching on set numbers:

```
123-1
1230-1
...
```

### Owned sets

```
owned
보유
```

With condition filter:

```
owned 1
보유 2
```

## Command Syntax

Commands are entered in the search box.

**Basic operations**

```
+0000-1		→ add to owned
-0000-1		→ remove from owned
2>0000-1	→ set condition to 2
[note]>0000-1	→ add note
```

Multiple commands can be used in a single input:

```
+1234-1 -5678-1 2>1234-1 [gift]>1111-1
```

## Notes

Notes are enclosed in square brackets:

```
[Note]>1111-1
```

**Examples**

```
[2026. 01. 01. Gift]>1111-1
[2026년 새해 선물]>1111-1
[!@#$%^&*()]>1111-1
```

**Escaping special characters**

You can include ``]`` or ``\`` using escape sequences:

```
[\]]>1234-1	→ ]
[\\]>1234-1	→ \
[a\]b]>1234-1	→ a]b
[a\\b]>1234-1	→ a\b
```

- Control characters (e.g. newline) are not allowed in notes.

## Details

**Condition values**

- ``0`` — default (light blue)
- ``1`` — bad (light pink)
- ``2`` — good (light green)

**Additional behavior**

- Notes are shown in both the main table and detail view
- Copy feature supports normalization (e.g. ``1234-1 → 1234``)
- Tooltip help is available via the ? button

## Data

- CSV data is **not included**
- Users must download data manually from Rebrickable
- Redistribution of the dataset is not recommended

## Disclaimer

- LEGO `<sup>`®`</sup>` is a trademark of the LEGO Group
- This project is not affiliated with the LEGO Group
- Data is provided by Rebrickable and is not redistributed here

## AI Usage Disclosure

Some parts of this project were developed with assistance from ChatGPT (OpenAI):

- Code drafting
- Refactoring and structure improvements

All final decisions and modifications were reviewed by the author.

## License

This project is licensed under the terms of the GPL-3.0 License.

See the [LICENSE](./LICENSE) ([ko-KR](https://www.olis.or.kr/license/Detailselect.do?lId=1072)) file for details.
