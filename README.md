# Congressional Bill Scraper

This is a simple scraper for [congress.gov](https://www.congress.gov/).

For more information about this project, see:
- [This blog post](https://hunterheidenreich.com/posts/us-117th-congress-data-exploration/) to understand the motivation behind this project and how the data was collected.

## Usage

```bash
python src/scraper.py
```

By default, this is set to scrape through Senate joint resolutions for the 117th Congress.
You can change this by modifying the `scraper.py` file, specifically the `main` function.
I've commented out the other targets as well as their respective `bill_id` ranges.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.