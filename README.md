# Flask Login Applikasjon

## Oversikt
Denne applikasjonen er for å skape en mer brukervenlig opplevelse til brukerne av tradingboten.

## Egenskaper
- Bruker Registrering

- Bruker Logg inn

- Passord Hashing

- Admin kontroll
## Teknologier
- Flask

- Flask_login

- SQLAlchemy 

- Flask_wtf

- Werkzeug

- Flask_migrate


## Oppsett Bruksanvisning

### 1. Klone Repository
```bash
git clone https://github.com/joakimrrtt/eksamen.git
````
### 2. Lag et virtual enviroment og aktiver den
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate
`````
### 3. Installer pakker fra requirements.txt
```bash
pip install -r requirements.txt
````
### 4. Start applikasjonen
```bash
python3 app.py
`````
### 5. Åpne i nettleser


## Routes
### Routes oversikt
- / = homepage

- /login = Login er der brukeren kan skrive inn brukernavnet og passordet for å få tilgang til videre innhold.

- /signup = Sign Up er der brukere blir skapt og passord kryptert

- /dashboard = Siden brukerene kommer til etter å ha logget inn.

- /logout