from requests import get
import requests
import re
import math
import random
import time
from multiprocessing import Pool
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim
from db_connector import *
from functools import partial
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from fake_useragent import UserAgent
import urllib.request

# geolocator=Nominatim(timeout=3)
ua = UserAgent()
header = {'User-Agent': str(ua.chrome)}
session = requests.Session()
retry = Retry(connect=5, backoff_factor=0.5)
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)
session.mount('https://', adapter)

def format_date(date):

    month = date[:-4]
    year = date[-4:]
    new_date = month + "1, " + year
    return new_date

# returns array of data to each review
def get_review_content(container):
        stars_span = container.find('span', class_='ui_bubble_rating')
        stars_string = str(stars_span)
        stars = re.findall(r'\d+',stars_string)[0]

        # get date of Review
        date_span = container.find('span', class_='ratingDate' )
        date_of_review = date_span['title']

        # get date of Visit
        visit_date =  container.find("div", class_='prw_rup prw_reviews_stay_date_hsx').get_text().replace('Date of visit: ',"")
        if(visit_date == ""):
            visit_date = date_of_review
        else:
            visit_date = format_date(visit_date)

        text = container.find('span', class_='noQuotes').get_text()

        return [stars,text,visit_date, date_of_review]

def format_date_hotel(date,type):
    if(type == 'review'):
        # print(date[-4])
        if(date[-4] != "2"):
            return ""
        else:
            year = date[-4:]
            month = date[:3]
            return month + " 1," + year


def get_review_content_hotel(container):
    stars_span = container.find('span', class_='ui_bubble_rating')
    stars_string = str(stars_span)
    stars = re.findall(r'\d+', stars_string)[0]

    # get date of Review
    date_div = container.find('div', class_='social-member-event-MemberEventOnObjectBlock__event_type--3njyv').find('span', recursive= False).get_text()
    # print(date_div)
    date_of_review = format_date_hotel(date_div[-8:],'review')

    # get date of Visit
    visit_date = container.find("div", class_='location-review-review-list-parts-EventDate__event_date--1epHa')
    if (visit_date == None):
        visit_date = date_of_review
    else:
        visit_date = "1" + visit_date.get_text()

    text_a = container.find('a', class_='location-review-review-list-parts-ReviewTitle__reviewTitleText--2tFRT')
    text = text_a.find('span', recursive=False).get_text()

    return [stars, text, visit_date, date_of_review]

def get_review_content_sight(container):
    stars_span = container.find('span', class_='ui_bubble_rating')
    stars_string = str(stars_span)
    stars = re.findall(r'\d+', stars_string)[0]

    # get date of Review
    date_div = container.find('div', class_='social-member-event-MemberEventOnObjectBlock__event_type--3njyv').find('span', recursive= False).get_text()
    # print(date_div)
    date_of_review = format_date_hotel(date_div[-8:],'review')

    # get date of Visit
    visit_span = container.find("span", class_='location-review-review-list-parts-EventDate__event_date--1epHa')
    if (visit_span == None):
        visit_date = date_of_review
    else:
        visit_text = visit_span.get_text()
        visit_date = "1" + re.sub("Date of experience: "," ", visit_text)
        if(date_of_review == ""):
            date_of_review = visit_date

    text_a = container.find('a', class_='location-review-review-list-parts-ReviewTitle__reviewTitleText--2tFRT')
    text = text_a.find('span', recursive=False).get_text()

    return [stars, text, visit_date, date_of_review]

def create_url(url, page_number):
        partitioned_url = url.partition('Reviews')
        loop_url = partitioned_url[0] + partitioned_url[1] + '-or' + str(page_number) + '0'+ partitioned_url[2]
        return loop_url


def create_url_hotel(url, page_number):
    partitioned_url = url.partition('Reviews')
    loop_url = partitioned_url[0] + partitioned_url[1] + '-or' + str(page_number*5) + partitioned_url[2]
    return loop_url

def check_date(date):
    # print(date)
    if(date== '' or date[-3:] == "ago" or date[-4:] == "2020"):
        return "skip"
    elif( 2020 > int(date[-4:]) > 2010):
        return "write"
    else:
        return "break"

# starting Point of single Restaurant/attraction  => "item"
def get_soup(url):
    response = session.get(url)
    return BeautifulSoup(response.text, 'lxml')

def iterate_activity(initial_url,id):
    # inital page of item
    try:
        initial_response = session.get(initial_url)
    except:
        return
    html_soup = BeautifulSoup(initial_response.text, 'lxml')

    # get Name and add to db
    item_soup = html_soup.find('h1', class_='ui_header')
    if (item_soup != None):
        item_name = item_soup.get_text()
    else:
        item_name = 'Name not Available'

    item_id = db_connector.write_activity( id, item_name,'restaurant')

    # number of review Pages for single Item
    number_of_pages_html = html_soup.find('a', class_='last')
    if(number_of_pages_html != None):
        number_of_pages = int(number_of_pages_html.get_text())
    else:
        number_of_pages = 1


    for i in range(number_of_pages):
        # print("i: " + str(i))
        if(i > 0):
            loop_url = create_url(initial_url, i)
            print(loop_url)
            # get Reviews

            try:
                loop_response = session.get(loop_url)
            except:
                continue
            html_soup = BeautifulSoup(loop_response.text, 'lxml')
            review_containers = html_soup.findAll('div', class_='review-container')

        else:
            review_containers = html_soup.findAll('div', class_='review-container')
            print(initial_url)
        z=1

        for EachPart in review_containers:
            # print("review: " + str(i)+ str(z))
            review_data = get_review_content(EachPart)

            print("restaurant: " + str(review_data))
            check = check_date(review_data[2])
            if(check == "write"):
                # write into Db
                db_connector.write_sentiment(item_id,review_data)
            elif(check =='break'):
                return
            else:
                # do nuttin
                pass

def iterate_sight(initial_url, id):
    try:
        initial_response = session.get(initial_url)
    except:
        return
    html_soup = BeautifulSoup(initial_response.text, 'lxml')

    # get Name and add to db
    item_soup = html_soup.find('h1', class_='ui_header h1')
    if (item_soup != None):
        item_name = item_soup.get_text()
    else:
        item_name = 'Name not Available'

    item_id = db_connector.write_activity(id, item_name, 'sight')

    number_of_pages = html_soup.find('span', class_='location-review-review-list-parts-LanguageFilter__paren_count--2vk3f')
    if(number_of_pages != None):
        number_of_pages = number_of_pages.get_text()
        # print(number_of_pages)
        number_of_pages = number_of_pages.replace("(", "").replace(")","").replace(",","")
        number_of_pages = math.ceil(int(number_of_pages) / 5)
    else:
        number_of_pages = 1

    for i in range(number_of_pages):
        # print("i: " + str(i))
        if (i > 0):
            bool = True

            loop_url = create_url_hotel(initial_url, i)
            print(loop_url)
            x = 0
            while(bool):
                try:
                    loop_response = session.get(loop_url, headers = header)
                except:
                    continue
                new_soup = BeautifulSoup(loop_response.text, 'lxml')
                print(new_soup.find('button', class_='_3WHa1yVQ _N28mfeX sriconym _1m8gT36z'))
                if(new_soup.find('button', class_='_3WHa1yVQ _N28mfeX sriconym _1m8gT36z') is None):
                    review_containers = new_soup.findAll('div', class_='location-review-card-Card__ui_card--2Mri0 location-review-card-Card__card--o3LVm location-review-card-Card__section--NiAcw')
                    bool = False
                if (x > 20) :
                    continue

                time.sleep(0.5)

        else:
            review_containers = html_soup.findAll('div', class_='location-review-card-Card__ui_card--2Mri0 location-review-card-Card__card--o3LVm location-review-card-Card__section--NiAcw')

        for EachPart in review_containers:
            review_data = get_review_content_sight(EachPart)
            print("sight: " +  str(review_data))

            check = check_date(review_data[2])
            # print("date" + review_data[2] +" Check " + check)
            if (check == "write"):
                # write into Db
                db_connector.write_sentiment(item_id, review_data)
            elif (check == 'break'):
                return
            else:
                # do nuttin
                pass

def iterate_hotel(initial_url, id):
    try:
        initial_response = session.get(initial_url)
    except:
        return
    html_soup = BeautifulSoup(initial_response.text, 'lxml')

    # get Name and add to db
    item_soup = html_soup.find('h1', class_='hotels-hotel-review-atf-info-parts-Heading__heading--2ZOcD')
    if(item_soup != None ):
        item_name = item_soup.get_text()
    else:
        item_name = 'Name not Available'
    print(item_name)
    item_id = db_connector.write_activity(id, item_name, 'hotel')

    number_of_pages = html_soup.findAll('span', class_='location-review-review-list-parts-LanguageFilter__paren_count--2vk3f')
    if(number_of_pages != []):
        number_of_pages = number_of_pages[1].get_text()
        # print(number_of_pages)
        number_of_pages = number_of_pages.replace("(", "").replace(")","").replace(",","")
        number_of_pages = math.ceil(int(number_of_pages) / 5)
    else:
        number_of_pages = 1
    print(number_of_pages)
    for i in range(number_of_pages):
        # print("i: " + str(i))
        if (i > 0):
            try:
                loop_url = create_url_hotel(initial_url, i)
            except:
                continue
            print(loop_url)
            # get Reviews
            loop_response = session.get(loop_url)
            html_soup = BeautifulSoup(loop_response.text, 'lxml')
            review_containers = html_soup.findAll('div', class_='hotels-community-tab-common-Card__card--ihfZB hotels-community-tab-common-Card__section--4r93H')
        else:
            review_containers = html_soup.findAll('div', class_='hotels-community-tab-common-Card__card--ihfZB hotels-community-tab-common-Card__section--4r93H')
        z = 1

        for EachPart in review_containers:
            review_data = get_review_content_hotel(EachPart)
            print("hotel: " +  str(review_data))
            check = check_date(review_data[2])
            if (check == "write"):
                # write into Db
                db_connector.write_sentiment(item_id, review_data)
            elif (check == 'break'):
                return
            else:
                # do nuttin
                pass

def create_next_page_url_restaurant(url, id,index):
     partitioned_url = url.partition('-'+id)
     url = partitioned_url[0][:-1] + 'Search' + partitioned_url[1] + "-oa" + str(index * 30 ) + partitioned_url[2]
     return url


def create_next_page_url_hotel(url, id, index):
    partitioned_url = url.partition('-' + id)
    url = partitioned_url[0]  + partitioned_url[1] + "-oa" + str(index * 30) + partitioned_url[2]
    return url

def create_next_page_url_sight(url, id, index):
    partitioned_url = url.partition('-a_allAttractions.true')
    url = partitioned_url[0] + "-oa" + str(index * 30) + partitioned_url[2]
    return url


def get_coordinates(name):
     geolocator = Nominatim(user_agent="specify_your_app_name_here")
     location = geolocator.geocode(name)
     point = (location.latitude, location.longitude)
     return point

def db_write_city(name):
    try:
        coordinates = get_coordinates(name)
        db_city_id = db_connector.write_city(name, coordinates)
        return db_city_id
    except:
        db_city_id = db_connector.write_city(name, (0,0))
        return db_city_id

def iterate_pages_restaurant(all_urls):
    return_urls = []
    for url in all_urls:
        try:
            response = session.get(url)
        except:
            return
        restaurants_html = BeautifulSoup(response.text, 'lxml')
        all_restaurants = restaurants_html.findAll('div' , class_='_1kNOY9zw')

        i = 1
        for restaurant in all_restaurants:
            if(restaurant.find('div' , class_='_376lhJeB fXv-kKaf') == None ):
                href = restaurant.find('a', class_= '_15_ydu6b')['href']
                restaurant_url = 'https://www.tripadvisor.com' + href
                # print("Restaurant: " + str(x*10 + i) + 'name: ' + href)
                print(restaurant_url)
                return_urls.append(restaurant_url)
    return return_urls

def iterate_pages_hotel(all_urls):
    # print(id)
    return_urls = []
    for url in all_urls:
        try:
            response = session.get(url)
        except:
            continue

        hotel_html = BeautifulSoup(response.text, 'lxml')
        all_hotels = hotel_html.findAll('div', class_='listing collapsed')


        i =0
        for hotel in all_hotels:
            print(i)
            if(hotel.find('span', class_='ui_merchandising_pill sponsored_v2') == None):
                # print(i)
                href = hotel.find('a' , class_= 'property_title prominent')['href']
                hotel_url = 'https://www.tripadvisor.com' + href
                i =i+1
                # print(href)
                return_urls.append(hotel_url)
    return return_urls

def iterate_pages_sight(all_urls):
    return_sights = []
    for url in all_urls:

        try:
            response = session.get(url)
        except:
            continue
        sights_html = BeautifulSoup(response.text, 'lxml')
        all_sights = sights_html.findAll('div', class_='attraction_element_tall')
        for sight in all_sights:
            href = sight.find('div' , class_= 'tracking_attraction_title listing_title').find('a', recursive= False)['href']
            sight_url = 'https://www.tripadvisor.com' + href
            # print(sight_url)
            # i =i+1
            return_sights.append(sight_url)

    return return_sights


def all_urls_of_city(city_url,city_id,type):
    init_restaurant_response = session.get(city_url)
    init_restaurant_html = BeautifulSoup(init_restaurant_response.text, 'lxml')
    # count number of pages to iterate
    all_page_numbers = init_restaurant_html.findAll('a', class_='pageNum')
    number_of_pages =  int(all_page_numbers[-1].getText())
    all_urls = []
    all_urls.append(city_url)
    for x in range(number_of_pages + 1):
        if x > 1:
            if(type == 'hotel'):
                next_page_url = create_next_page_url_hotel(city_url, city_id, x - 1)
            elif(type == 'sight'):
                next_page_url = create_next_page_url_sight(city_url, city_id, x - 1)
            else:
                next_page_url = create_next_page_url_restaurant(city_url, city_id, x - 1)
            all_urls.append(next_page_url)
    return all_urls

restaurant_url = "https://www.tripadvisor.com/Restaurants-g60898-Atlanta_Georgia.html"
hotel_url = "https://www.tripadvisor.com/Hotels-g60898-Atlanta_Georgia-Hotels.html"
sight_url = 'https://www.tripadvisor.com/Attractions-g60898-Activities-a_allAttractions.true-Atlanta_Georgia.html'
city_name = "Atlanta"
tripadvisor_city_id = "g60898"

if __name__ == '__main__':
    db_city_id = db_write_city(city_name)

    restaurant_pages_urls = all_urls_of_city(restaurant_url, tripadvisor_city_id,'rest')
    all_restaurants  = iterate_pages_restaurant(restaurant_pages_urls)
    all_restaurants = list(dict.fromkeys(all_restaurants))
    random.shuffle(all_restaurants)
    restaurant_helper = partial(iterate_activity, id = db_city_id)
    p = Pool(processes=4)
    p.map(restaurant_helper, all_restaurants)
    p.close()
    p.join()

    hotel_pages_urls = all_urls_of_city(hotel_url,tripadvisor_city_id,'hotel')
    all_hotels = iterate_pages_hotel(hotel_pages_urls)
    all_hotels = list(dict.fromkeys(all_hotels))
    random.shuffle(all_hotels)
    hotel_helper = partial(iterate_hotel ,id = db_city_id)
    x= Pool(processes=4)
    x.map(hotel_helper, all_hotels)
    x.close()
    x.join()
    #
    sight_pages_urls = all_urls_of_city(sight_url, tripadvisor_city_id, "sight")
    all_sights = iterate_pages_sight(sight_pages_urls)
    all_sights = list(dict.fromkeys(all_sights))
    random.shuffle(all_sights)
    sight_helper = partial(iterate_sight ,id = db_city_id)
    a = Pool(processes=4)
    a.map(sight_helper, all_sights)
    a.close()
    a.join
