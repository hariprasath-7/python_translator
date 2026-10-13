from deep_translator import GoogleTranslator
import time

translator = GoogleTranslator(source="en", target="ta")

while True:
    text = input("\nEnter English text (or 'exit' to quit): ")

    if text.lower() == "exit":
        print("Translator closed!")
        break

    try:
        translated_text = translator.translate(text)
        print("Tamil Translation:", translated_text)

    except Exception as e:
        print("Translation failed:", e)
        print("Please wait a few minutes and try again.")
        time.sleep(5)