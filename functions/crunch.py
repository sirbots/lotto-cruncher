from bs4 import BeautifulSoup
import re
import requests
import pandas as pd
import time
from random import randrange

# my functions
from send_email import send_lotto_update_email


# Get the individual game odds from each game page
domain = 'https://www.illinoislottery.com'
games_page_path = '/games-hub/instant-tickets'
games_page_query = '?page='

i = 0
hrefs = []

for i in range(4):
    lotto_main_page_response = requests.get(domain+games_page_path+games_page_query + str(i))
    lotto_main_page = lotto_main_page_response.content
    lotto_main_soup = BeautifulSoup(lotto_main_page, 'html.parser')

    game_page_links = lotto_main_soup.select('a.simple-game-card-prize__link')
    
    for a in game_page_links:
        link = a['href']
        hrefs.append(domain+link)

    # take a breath and go easy on the site
    time.sleep(randrange(1,3))

odds_dict = {}

# loop through each of the hrefs, go to that page and pull in the odds ratio, clean it up, and add it to the odds
# dictionary
for href in hrefs:
    # scrape the overall game odds from each game page
    single_game_page_response = requests.get(href)
    single_game_page = single_game_page_response.content
    single_game_soup = BeautifulSoup(single_game_page, 'html.parser')

    game_number_raw = str(single_game_soup.select('tr td')[11])
    game_number_clean = int(re.search('\d\d\d\d?',game_number_raw).group(0))
    
    try:
        odds_raw = str(single_game_soup.select('tr td')[3])
        odds_clean = re.search('\d\.\d\d',odds_raw).group(0)
        odds_clean_float = float(odds_clean)
    except:
        odds_clean = 0

    odds_dict[game_number_clean] = odds_clean_float
    time.sleep(randrange(1,3))
    

# Pull in outstanding ticket data for each game
lotto_unpaid_page_response = requests.get('https://www.illinoislottery.com/about-the-games/unpaid-instant-games-prizes')
lotto_unpaid_page = lotto_unpaid_page_response.content
lotto_unpaid_soup = BeautifulSoup(lotto_unpaid_page, 'html.parser')


# Create lists of all the games data
names = []
prices = []
ids = []
weeks = []
values = []
total_prizes = []
unclaimed_prizes = []

table_rows = lotto_unpaid_soup.select('tbody tr')

for row in table_rows:
    # add game names to list
    game_name = row.select('td')[0].get_text()
    names.append(game_name)
    
    # add single-ticket price to list
    game_price = int(row.select('td')[1].get_text().strip('$'))
    prices.append(game_price)
    
    # add game ID to list
    game_number = int(row.select('td')[2].get_text().split('(')[0])
    ids.append(game_number)
    
    # add weeks in market to list
    game_weeks_in_market = int(row.select('td')[2].get_text().split('(')[1].strip(')'))
    weeks.append(game_weeks_in_market)
    
    # add prize values to list
    prize_values_raw = row.select('td')[3].get_text()
    prize_values_strip_whitespace = re.sub('\s','',prize_values_raw)
    prize_values_strip_commas = re.sub('\,','',prize_values_strip_whitespace)
    prize_values_array = prize_values_strip_commas.split('$')
    prize_values_array = prize_values_array[1:]
    prize_values_array_as_int = [int(value) for value in prize_values_array]
    values.append(prize_values_array_as_int)

    # add total prizes to list
    total_prizes_total_raw = row.select('td')[4].get_text('<br>')
    total_prizes_total_stripped = re.sub('\,','',total_prizes_total_raw)
    total_prizes_total_clean = total_prizes_total_stripped.split('<br>')
    total_prizes_total_as_int = [int(value) for value in total_prizes_total_clean]
    total_prizes.append(total_prizes_total_as_int)

    # add unclaimed prizes to list
    unclaimed_prizes_total_raw = row.select('td')[5].get_text('<br>')
    unclaimed_prizes_total_stripped = re.sub('\,','',unclaimed_prizes_total_raw)
    unclaimed_prizes_total_clean = unclaimed_prizes_total_stripped.split('<br>')
    unclaimed_prizes_total_as_int = [int(value) for value in unclaimed_prizes_total_clean]
    unclaimed_prizes.append(unclaimed_prizes_total_as_int)

# create the dataframe
df = pd.DataFrame(list(zip(names,prices,ids,weeks,values,total_prizes,unclaimed_prizes)),
                         columns = ['game','ticket_price','ID','weeks','payouts','total_prizes','unclaimed_prizes'])

df['starting_odds'] = df['ID'].map(odds_dict)


def calc_expected_roi(row):
    '''Calculate current expected payout of a single play.'''

    pct_tickets_remaining = int(row['unclaimed_prizes'][0]) / int(row['total_prizes'][0])
    tickets_remaining = row['available_tickets_start'] * pct_tickets_remaining
    
    payout_pool = 0
    for i in range(0,len(row['payouts'])):
        payout_pool += (int(row['payouts'][i]) * int(row['unclaimed_prizes'][i]))
    
    expected_payout = 0
    expected_payout_clean = 0
    if not tickets_remaining == 0:
        expected_payout = payout_pool / (tickets_remaining * row['ticket_price']) - 1 
        expected_payout_clean = round(expected_payout * 100,1)
    
    return expected_payout_clean


def calc_available_tickets_start(row):
    '''Calculate the total number of starting available tickets'''

    total_prize_count = 0
    for item in row['total_prizes']:
        total_prize_count += item
    
    available_tickets_start = total_prize_count * row['starting_odds']
    return available_tickets_start


df['available_tickets_start'] = df.apply(calc_available_tickets_start,axis=1)
df['ROI'] = df.apply(calc_expected_roi,axis=1)

sorted_by_roi = df.sort_values('ROI',ascending=False)
sorted_by_roi.reset_index(inplace=True,drop=True)

# Build the body of the email
top_names = []
top_rois = []
email_body = 'Here are today\'s expected ROIs:\n\n'

for index, row in sorted_by_roi.iterrows():
    if index < 5:
        top_names.append(row['game'])
        top_rois.append(str(row['ROI']))
        
for i in range(0,len(top_names)):
    email_body += top_names[i] + " >>> " + top_rois[i] + '%\n'

# send the email!
send_lotto_update_email(email_body)