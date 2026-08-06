# Bundled fonts

The repository includes regular and bold faces only when redistribution terms are included with the files.

| Use | Included family | Directory |
| --- | --- | --- |
| Latin scripts | Poppins | `assets/fonts/poppins` |
| Editorial/display serif | Playfair Display | `assets/fonts/playfair_display` |
| Japanese | LINE Seed JP | `assets/fonts/line_seed_jp` |
| Thai | Kanit | `assets/fonts/kanit` |
| Vietnamese | Be Vietnam Pro | `assets/fonts/be_vietnam_pro` |
| Arabic | Kufam | `assets/fonts/kufam` |
| Arabic geometric/display alternative | Reem Kufi Fun | `assets/fonts/reem_kufi_fun` |
| Hindi and Devanagari | Noto Sans Devanagari | `assets/fonts/noto_sans_devanagari` |
| General fallback | Noto Sans | `assets/fonts/noto_sans` |

The OFL families copied from project font packs include all supplied static/variable files and their license notices, not only Regular/Bold. Use `assets/font-catalog.json` to search exact family, subfamily, PostScript name, scripts, hashes, and license paths. Regenerate it after font changes:

```powershell
python scripts/index_font_assets.py assets/fonts assets/font-catalog.json
```

Use `assets/font-presets.json` as a conservative starting point and override any family in project JSON. Validate every configured path with `scripts/check_text_runtime.py`; presence in the catalog does not prove that a font is appropriate for a specific role.

## Fonts users install themselves

Some useful fonts do not permit font-file redistribution or were supplied without sufficiently clear redistribution terms. They are intentionally not committed to this repository.

- Chinese: MiSans may be used from a user-installed local path after accepting its license, but its font software is not bundled or committed because redistribution is prohibited.
- Korean: S-Core Dream files found in prior local work are not bundled because no redistributable license notice accompanied that package. Obtain it from its publisher or use a confirmed open family such as Noto Sans KR.

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
