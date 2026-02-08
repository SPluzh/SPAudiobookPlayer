# How to Add a New Language

## Overview
The application now supports dynamic language loading. You can add new translations by simply placing a `.json` file into the `resources/translations` folder.

## Steps
1. **Create Translation File**
   - Create a new JSON file in `resources/translations/` (e.g., `de.json` for German, `fr.json` for French).
   - Use the language code as the filename.

2. **Define Language Metadata**
   - At the root of your JSON detailed structure, you MUST add a `"language_name"` key. This is what will be displayed in the menu.
   
   Example (`de.json`):
   ```json
   {
       "language_name": "Deutsch",
       "window": {
           "title": "SP Hörbuch Player"
       },
       "menu": {
           "menu": "Menü",
           ...
       }
       ...
   }
   ```

3. **Verify**
   - Restart the application.
   - Go to `View -> Language`.
   - Your new language should appear in the list.

## Missing Keys
If a translation key is missing in your language file, the application will fallback to English automatically.
You can check `resources/translations/missing_keys.json` (if generated) to see which keys are being requested but not found.

## Helper Script
You can use `tests/check_translations.py` to compare your new file against `en.json` to identify missing keys.
