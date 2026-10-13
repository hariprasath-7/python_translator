import sys
import time
from deep_translator import GoogleTranslator, MyMemoryTranslator
from deep_translator.exceptions import TooManyRequests

# Ensure UTF-8 encoding in Windows terminals for Tamil unicode characters
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")

google_translator = GoogleTranslator(source="en", target="ta")
mymemory_translator = MyMemoryTranslator(source="en-GB", target="ta-IN")

# If Google is rate-limiting the IP (HTTP 429), switch to MyMemory
use_mymemory = False


def translate(text: str) -> str:
    global use_mymemory

    if not use_mymemory:
        try:
            return google_translator.translate(text)
        except TooManyRequests:
            print("\n[Notice] Google Translate rate limit reached. Switching to MyMemory translator...")
            use_mymemory = True
        except Exception as e:
            print(f"\n[Notice] Google Translate unavailable ({e}). Trying fallback translator...")
            use_mymemory = True

    return mymemory_translator.translate(text)


print("--- English to Tamil Translator ---")
while True:
    try:
        text = input("\nEnter English text (or 'exit' to quit): ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nTranslator closed!")
        break

    if not text:
        continue

    if text.lower() == "exit":
        print("Translator closed!")
        break

    try:
        translated_text = translate(text)
        print("Tamil Translation:", translated_text)

    except Exception as e:
        print("Translation failed:", e)
        print("Please wait a few minutes and try again.")
        time.sleep(2)