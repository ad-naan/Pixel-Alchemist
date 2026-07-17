# Bundled fonts

The repository includes regular and bold faces only when redistribution terms are included with the files.

| Locale family | Included family | Directory |
| --- | --- | --- |
| Latin scripts | Poppins | `assets/fonts/poppins` |
| Japanese | LINE Seed JP | `assets/fonts/line_seed_jp` |
| Thai | Kanit | `assets/fonts/kanit` |
| Vietnamese | Be Vietnam Pro | `assets/fonts/be_vietnam_pro` |
| Arabic | Kufam | `assets/fonts/kufam` |
| Hindi and Devanagari | Noto Sans Devanagari | `assets/fonts/noto_sans_devanagari` |
| General fallback | Noto Sans | `assets/fonts/noto_sans` |

Use `assets/font-presets.json` as a starting point and override any family in the project JSON. Validate every configured path with `scripts/check_text_runtime.py`.

## Fonts users install themselves

Some useful fonts do not permit font-file redistribution or were supplied without sufficiently clear redistribution terms. They are intentionally not committed to this repository.

- Chinese: download MiSans from the [official MiSans download page](https://hyperos.mi.com/font/en/download/), accept its license, and configure the local file under the `zh` key. The official agreement allows created artwork to be distributed but prohibits redistributing the font software itself.
- Korean: obtain S-Core Dream from its official publisher or choose an OFL Korean family such as Noto Sans KR, then configure the local `ko` paths. Confirm the current license at the download source before use.

Example local override:

```json
{
  "fonts": {
    "zh": {
      "regular": "C:/local-fonts/chinese-regular.ttf",
      "bold": "C:/local-fonts/chinese-bold.ttf"
    },
    "ko": {
      "regular": "C:/local-fonts/korean-regular.otf",
      "bold": "C:/local-fonts/korean-bold.otf"
    }
  }
}
```

Each bundled font directory contains its license notice. Keep those notices when redistributing the repository.
