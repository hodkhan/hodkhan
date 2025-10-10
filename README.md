# HodKhan، Khabar Khan Solomon(Solomon's Newsreader)


* HodHod is a personal newspaper displaying news according to people's interests

![hodkhan img](https://github.com/user-attachments/assets/b2adf9e6-079b-4ba7-9483-89305987534a)

# Hodkhan website 
[Hodkhan](https://hodkhan.ir)

## Installation

* download from Github
```bash
git clone https://github.com/mahdiahmadi87/hodhod.git
```

* download Gemma Embedding Model
[Download from Hugging Face](https://huggingface.co/google/embeddinggemma-300m)

* Install requirements
```bash
pip install -r requirements.txt
```

* Migrate django
```bash
cd hodkhan
python3 manage.py migrate
```

* Create a superuser
```bash
python3 manage.py createsuperuser
```


## Usage
* WebSite:
```bash
cd hodkhan
python3 manage.py runserver
```

* Crawler:
```bash
cd crawlers
python3 manage.py crawl_feeds 
```

* Regressos:
```bash
cd newsSelection
python3 regressor.py
```

## License

[Apache](http://www.apache.org/licenses/)
