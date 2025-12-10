import pandas as pd
import sys
from pathlib import Path

def main():
    # 1. Define the test data
    test_glossary_data = [
        {
            "source": "Login",
            "target": "Connexion",
            "lang": "fr",
            "match_type": "exact",
            "case_sensitive": True,
            "context": "Button label",
            "is_forbidden": False
        },
        {
            "source": "Welcome",
            "target": "Bienvenue",
            "lang": "fr",
            "match_type": "partial",
            "case_sensitive": False,
            "context": "Greeting",
            "is_forbidden": False
        },
        {
            "source": "Submit",
            "target": "Enviar",
            "lang": "es",
            "match_type": "exact",
            "case_sensitive": False,
            "context": "Form submission",
            "is_forbidden": False
        },
        {
            "source": "DO NOT TRANSLATE",
            "target": "",
            "lang": "",
            "match_type": "partial",
            "case_sensitive": False,
            "context": "System code",
            "is_forbidden": True
        },
        {
            "source": "Cancel",
            "target": "Abbrechen",
            "lang": "de",
            "match_type": "exact",
            "case_sensitive": True,
            "context": "Dialog action",
            "is_forbidden": False
        }
    ]

    # 2. Convert to DataFrame
    df = pd.DataFrame(test_glossary_data)

    # 3. Rename columns to match what utils/glossary.py expects
    df = df.rename(columns={
        "source": "source_text",
        "target": "target_text",
        "lang": "language_code"
    })

    # 4. Save to Excel
    # Output to the current directory so the Action can find it easily
    output_file = "glossary.xlsx"
    df.to_excel(output_file, index=False)

    print(f"Successfully created '{output_file}' with {len(df)} entries.")

if __name__ == "__main__":
    main()
