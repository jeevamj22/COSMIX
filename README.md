# COSMIX

COSMIX checks a cosmetic ingredient list against a person's skin profile.

It answers a shopping question: given this product and this person, is there a direct conflict, and what is the short-term and long-term picture? It does not diagnose skin from a photo, and it does not promise that a product will work.

## Run it

1. Install Python 3.12 from [python.org](https://www.python.org/downloads/) if you do not have it. Tick "Add python.exe to PATH".
2. Double-click `run.bat` in this folder.
3. Leave the black window open. The app opens at http://127.0.0.1:8000
4. Close the window to stop COSMIX.

Your profiles, checks, and photos are stored in `%LOCALAPPDATA%\COSMIX` on this computer. They are not stored in this project folder, so OneDrive does not upload them.

## How to use it

1. Open **Your profile**. Enter skin type, tone, allergies, and medicines. Or click **Use an example profile**.
2. Open **Check a product**. Paste a shop link and click **Read this page**, or paste the ingredient list yourself.
3. Edit the list if the page was read wrong. Then click **Check against my profile**.
4. Read the short-term and long-term result. A photo can be attached for your own record. The photo is not analysed.

Skin tone is used for pigmentation risk. COSMIX does not recommend products for lightening skin.

## What is in this folder

- `app` is the product.
- `run.bat` starts it.
- `sources` keeps the chemical PDF you uploaded. That file is a Royal Society of Chemistry classroom worksheet for teenagers, not a safety database. Some of its lines are wrong, so the checker does not use it as medical advice.
- `legacy` is the earlier "chat with a PDF" experiment. Do not run that for real checks. It can invent an answer.

## Before you put this on the internet

The old `env.example` file contained live secret keys, and that file was pushed to GitHub. Treat those keys as stolen.

1. Revoke the OpenAI key in your OpenAI account.
2. Revoke the Hugging Face token in your Hugging Face account.
3. Deleting the keys from the file is not enough. They remain in the Git history until the keys are revoked.

Do not commit a new key. This app does not need one.
