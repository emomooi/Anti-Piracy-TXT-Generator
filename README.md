# DecoyTXT - Anti-Piracy Decoy TXT Generator

A practical utility built with Python + Tkinter. Designed for novel authors plagued by piracy, it generates "fake TXT packages" to combat pirate websites and guide readers back to legitimate channels.

## Core Principle

Pirate websites typically scrape TXT packages released by authors. This tool employs a "honeypot" strategy:
1. **Keep Real Content**: The first N free chapters and the last N chapters (e.g., the grand finale) remain untouched.
2. **Replace Paid Chapters**: For paid chapters, only the **chapter beginning** and **chapter ending** are kept, while the middle section is replaced with text from free chapters.
3. **Perfect Word Count Disguise**: The program precisely calculates the character count of the original middle section (including line breaks) and strictly extracts filler text of the exact same length. This ensures the total character count of the fake package matches the original **perfectly**, preventing detection by automated scripts.
4. **Effect**: Readers on pirate websites will find the plot disconnected and will actively search for the legitimate source.

## Features

- [x] Customizable first N free chapters (remain untouched)
- [x] Customizable last N chapters to keep (remain untouched, preventing "bad ending" detection)
- [x] Customizable character count to keep at the beginning and end of each chapter (e.g., 1000 characters each, to ensure plot coherence)
- [x] **Perfect Word Count Consistency** (zero character count difference before and after generation)
- [x] Supports multiple output encodings: `UTF-8 (no BOM)`, `UTF-8 (with BOM)`, `ANSI (GBK)`
- [x] Supports custom regex for chapter titles (compatible with formats like "Chapter 1" with spaces)
- [x] Supports random seeds for reproducing specific generation results

## Interface Preview

*(It is highly recommended to place a screenshot of your software here, such as `screenshot.png`, to greatly increase the project's credibility)*

## How to Use (Run from Source)

1. Install Python 3.8 or above.
2. Clone this project:
   ```bash
   git clone https://github.com/your-username/DecoyTXT.git
