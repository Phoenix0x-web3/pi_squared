# Phoenix Dev

More info:  
[Telegram Channel](https://t.me/phoenix_w3)  
[Telegram Chat](https://t.me/phoenix_w3_space)

[Инструкция на русcком](https://phoenix-14.gitbook.io/phoenix/proekty/pi-squared)</br>


## PI Squared Network

Pi Squared Network is building the Verifiable Settlement Layer (VSL) — a decentralized infrastructure for fast, scalable, and cryptographically verifiable transactions between applications, blockchains, and AI agents.

## Functionality
- Register with email(dmx, icloud)
- Pi2 Reactor
- Quests


## Requirements
- Python version 3.10 - 3.12 
- Emails
- Proxy (optional)
- Twitter auth tokens (optional) 


## Installation
1. Clone the repository:
```
git clone https://github.com/Phoenix0x-web3/pi_squared.git
cd pi_squared
```

2. Install dependencies:
```
python install.py
```

3. Activate virtual environment: </br>

`For Windows`
```
venv\Scripts\activate
```
`For Linux/Mac`
```
source venv/bin/activate
```

4. Run script
```
python main.py
```

## Project Structure
```
pharos_network/
├── data/                   #Web3 intarface
├── files/
|   ├── email_data.txt      # Emails for register
|   ├── twitter_tokens.txt  # Twitter auth tokens (optional)
|   ├── reserve_twitter.txt # Reserved Twitter auth tokens
|   ├── proxy.txt           # Proxy addresses (optional)
|   ├── reserve_proxy.txt   # Reserved Proxy addresses (optional)
|   ├── wallets.db          # Database
│   └── settings.yaml       # Main configuration file
├── functions/              # Functionality
└── utils/                  # Utils
```
## Configuration

### 1. files folder
- `email_data.txt`: One email per line(format: `email:password`). Work with dmx and icloud emails
- `proxy.txt`: One proxy per line (format: `http://user:pass@ip:port`)
- `reserve_proxy.txt`: One proxy per line (format: `http://user:pass@ip:port`)
- `twitter_tokens.txt`: One token per line 
- `reserve_twitter.txt`: One token per line 

### 2. Main configurations
```yaml
# Number of threads to use for processing wallets
threads: 1

# Number of retries for failed action
retry: 3

#BY DEFAULT: [0,0] - all wallets
#Example: [2, 6] will run wallets 2,3,4,5,6
#[4,4] will run only wallet 4
range_wallets_to_run: [0, 0]

#Check for github updates
check_git_updates: true

# BY DEFAULT: [] - all wallets
# Example: [1, 3, 8] - will run only 1, 3 and 8 wallets
exact_wallets_to_run: []

# the log level for the application. Options: DEBUG, INFO, WARNING, ERROR
log_level : INFO

# Delay before running the same wallet again after it has completed all actions (1 - 2 hrs default)
random_pause_wallet_after_completion:
  min: 3600
  max: 7200

# Random pause between actions in seconds
random_pause_between_actions:
  min: 5
  max: 60

#Maximum possible number of errors before replacement proxy/twitter
resources_max_failures: 3
#Perform automatic replacement from proxy reserve files
auto_replace_proxy: true
#Perform automatic replacement from twitter reserve files
auto_replace_twitter: false  

# Telegram Bot ID for notifications
tg_bot_id: ''

# You can find your chat ID by messaging @userinfobot or using https://web.telegram.org/. (example 1540239116)
tg_user_id: ''
```

### 3. Module Configurations

**Emails**:
```yaml
#Server for IMAP support gmx and icloud
#For icloud use imap.mail.me.com
imap_server: imap.gmx.com
#Port for IMAP
imap_port: 993
```
**Pi2 Reactor**:
```yaml
#Games
games:
  min: 30
  max: 40

#Clicks: !Maximum is 170
clicks:
  min: 60
  max: 154
```

## Usage

For register to portal you need email addresses. 

On first use, you need to fill in the `email_data.txt`, `proxy.txt`, `twitter.txt` files. After launching the program, go to `DB Actions → Import wallets to Database`.

<img src="https://imgur.com/UjvH1Lr.png" alt="Preview" width="600"/>

If you want to update proxy or twitter tokens you need to make synchronize with DB. After you made changes in files proxy.txt, twitter_tokens.txt, please choose this option.

<img src="https://imgur.com/O5cjvsK.png" alt="Preview" width="600"/>

Once the database is created, you can start the project by selecting `Pi Squared → Run All Tasks or other options`.

<img src="https://imgur.com/Tr2lVx2.png" alt="Preview" width="600"/>





