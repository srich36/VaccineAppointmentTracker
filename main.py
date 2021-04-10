import sys
import requests
import pytz
from geopy import distance
from dateutil import parser
from datetime import datetime


url = 'https://www.vaccinespotter.org/api/v0/states/CA.json'

output_str = ''


class CustomOutput:
    """
    Capture everything we send to stdout into a variable so we can send it in an email notification too
    """

    def __init__(self, stream):

        self.stream = stream

    def write(self, data):
        global output_str
        self.stream.write(data)
        self.stream.flush()
        output_str += data

    def flush(self):
        pass


sys.stdout = CustomOutput(sys.stdout)


class VaccineTypes:
    UNKNOWN = 'unknown'
    PFIZER = 'pfizer'
    MODERNA = 'moderna'
    JJ = 'jj'
    ALL = 'all'


class SortOrder:
    LOCATION = 'distance_away'
    APPOINTMENTS_LAST_FETCHED = 'last_fetched_ago'
    APPOINTMENTS_LAST_MODIFIED = 'last_modified_ago'


#### CONFIGURATION ####
current_lat = 37.40758515947319
current_long = -121.9368054864926
current_location = (current_lat, current_long)

# Distance Threshold in miles
threshold = 50

sort_orders = set([SortOrder.APPOINTMENTS_LAST_MODIFIED, SortOrder.LOCATION])
desired_types = set([VaccineTypes.UNKNOWN, VaccineTypes.PFIZER,
                     VaccineTypes.MODERNA, VaccineTypes.ALL, VaccineTypes.JJ])
#### CONFIGURATION ####

current_time = datetime.utcnow().replace(tzinfo=pytz.utc)


def get_distance_away(site):
    coords = site['geometry']['coordinates']
    # Reversed in api
    long, lat = coords
    site_coords = (lat, long)
    return distance.distance(current_location, site_coords).miles


def under_distance_threshold(site):
    return get_distance_away(site) <= threshold


def has_desired_vaccine_type(vaccine_types):
    if VaccineTypes.ALL in desired_types:
        return True
    return bool(next((vaccine_type for vaccine_type in vaccine_types if vaccine_type.lower() in desired_types), False))


def output_date_delta(td_object):
    seconds = int(td_object.total_seconds())
    periods = [
        ('year',        60*60*24*365),
        ('month',       60*60*24*30),
        ('day',         60*60*24),
        ('hour',        60*60),
        ('minute',      60),
        ('second',      1)
    ]

    strings = []
    for period_name, period_seconds in periods:
        if seconds > period_seconds:
            period_value, seconds = divmod(seconds, period_seconds)
            has_s = 's' if period_value > 1 else ''
            strings.append("%s %s%s" % (period_value, period_name, has_s))

    return ", ".join(strings)


separator = '-' * 80


def send_email_notification(sites):
    # TODO: Implement
    # Get site IDs (site["properties"]["id"])
    # Check lockfile (and lockfile created date for each site)
    # Load to emails from config dynamically here 
    # If any sites don't have lockfiles, send content in output_str in email
    pass


def output_site(site, index):
    appointments = site["properties"]["appointments"]
    appointment_types = set()
    for appointment in appointments:
        for appointment_type in appointment.get('appointment_types', []):
            appointment_types.add(appointment_type)

    print(f'{index}.')
    print(f'Distance: {site["distance_away"]}')
    print(f'URL: {site["properties"]["url"]}')
    print(
        f'Place: {site["properties"]["name"]} - {site["properties"]["address"]}')
    print(f'Zip code: {site["properties"]["postal_code"]}')
    print(f'Number of appointments: {len(site["properties"]["appointments"])}')
    print(
        f'Vaccine types: {",".join(site["properties"]["appointment_vaccine_types"])}')
    print(f'Appointment types: {",".join(appointment_types)}')
    print(f'Last modified ago: {output_date_delta(site["last_modified_ago"])}')
    print(f'Last fetched ago: {output_date_delta(site["last_fetched_ago"])}')
    print(separator)


res = requests.get(url)
if not 200 >= res.status_code <= 300:
    print('Error retrieving')
    sys.exit(1)

vaccines_checked = res.json()['features']
availble_vaccines = [location for location in vaccines_checked
                     if location['properties']['appointments_available'] is True and
                     len(location['properties']['appointments']) > 0
                     and has_desired_vaccine_type(location['properties']['appointment_vaccine_types'])
                     ]

close_sites = [
    site for site in availble_vaccines if under_distance_threshold(site)]
for close_site in close_sites:
    close_site['distance_away'] = get_distance_away(close_site)
    appointments_last_modified = parser.parse(
        close_site["properties"]["appointments_last_modified"])
    appointments_last_fetched = parser.parse(
        close_site["properties"]["appointments_last_fetched"])
    last_modified_ago = current_time - appointments_last_modified
    last_fetched_ago = current_time - appointments_last_fetched
    close_site['last_modified_ago'] = last_modified_ago
    close_site['last_fetched_ago'] = last_fetched_ago


num_sites = len(close_sites)
print(f'{num_sites} sites found')

for sort_order in sort_orders:
    print()
    print(separator)
    print(f'Sorting by: {sort_order}')
    close_sites.sort(key=lambda site: site[sort_order])
    for idx, result in enumerate(close_sites):
        output_site(result, idx + 1)


if num_sites > 0:
    send_email_notification(close_sites)

