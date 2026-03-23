# LEGO DB (Unofficial)

A local SQLite + GUI application for browsing and managing LEGO sets based on Rebrickable data.

This project is **not affiliated with the LEGO Group**.

## Features

- Local SQLite database
- Search by set number (prefix match)
- Owned sets management
- Condition tracking (0 / 1 / 2)
- Notes per set
- Related sets (same theme & year)
- Multi-language support (Korean / English) | 한국어 / 영어 지원

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

→ Prefix search for set numbers

Example results:

```
123-1
1230-1
...
```

### Owned sets

```
보유
owned
```

With condition filter:

```
보유 1
보유 2
owned 1
owned 2
```

## Command Syntax

Input via search box:

```
+0000-1		add owned
-0000-1		remove owned
2>0000-1	change condition
[note]>0000-1	add note
```

Multiple commands allowd:

```
+1234-1 -5678-1 2>1111-1 [gift]>2222-1
```

## Details

- Condition values:
  - 0: default (light blue)
  - 1: bad (light pink)
  - 2: good (light green)
- Notes are visible in main table and detail window
- Copy feature supports normalize option (1234-1 > 1234)
- Tooltip help available via '?' button

## Notes

- CSV data is **not included**
- Users must download data manually
- Redistribution of dataset is not recommended

## Disclaimer

- LEGO<sup>®</sup> is a trademark of the LEGO Group
- This project is not affiliated with LEGO Group
- Data is provided by Rebrickable and not redistributed here

## AI Usage Disclosure

Some parts of this project were developed with assistance from ChatGPT (OpenAI):

- Code drafting
- Refactoring & structure improvement

All final decisions and modifications were reviewed by the author.

## License

This project is licensed under the terms of the [GPL-3.0 license](./LICENSE) [(ko-KR)](https://www.olis.or.kr/license/Detailselect.do?lId=1072). See the LICENSE file for details.
