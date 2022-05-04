# Ensuring Clinician Safety Through Geofencing

This system aims to ensure that all mobile clinicians of a health startup are safe and within their designated locations. It monitors their locations in real-time and sends alerts if any of them leave their safe area.

## How?

Firstly, this service, written in Python 3, is run on one of [UCLA's SEASnet Linux Servers](https://www.seasnet.ucla.edu/lnxsrv/), which has email capabilities. Any user with a SEASnet account can send emails using the `mail` command in `bash`. Find the main code for this system in service.py.

As stated in the specification, there are a total of 6 phlebotomists/clinicians to be monitored for a total of one hour (3600 seconds). If any of these clinicians exits their designated safe zone during the time that this service is run, an email alert is sent.

For this task, I decided that 5 seconds would be an accurate and apt monitoring interval, because 6 GET requests have to be made during each interval, implying 1.2 QPS, which is reasonable and far below the specified limit of 100. Email alerts are sent in a few seconds, again well below the limit of 5 minutes (300 seconds). This implies that we can get several more clinicians (500) on this system with our current query frequency. Should our number of clinicians go even higher, we can work around this with two simple options:

- Reduce our monitoring interval: our interval can be increased significantly while staying within the 5-minute limit.
- Query in batches. For example, if we have 10000 clinicians, we can query 200 of them every 5 seconds (40 QPS), implying that our worst-case detection time would be 250 seconds, which is still within our time limit of 5 minutes.

At a high level, the program effectively flows as follows:

1. Retrive location information on all 6 clinicians from the API.
2. If, for whatever reason, the endpoint doesn't return, send an email alert and retry after the monitoring interval. This alert is sent once every minute at maximum.
3. If any clinician was previously in their safe zone but is now outside it, trigger an email alert. If this is not the first time they left the zone, include the number of times they left in the email.
4. Repeat 720 times (5 seconds * 720 = 3600 seconds = 1 hour).

### Packages/Libraries used

- os
- logging
- requests
- time
- datetime
- shapely

## Future Enhancements

I designed the current system with the assumption that the following will be the real-life user flow:

1. The clinician is in their safe zone.
2. The clinician leaves their safe zone and the company is alerted.
3. The company communicates with the clinician and instructs them to re-enter the safe zone.
4. Since the clinician is back in their safe zone, we must alert the company if they leave again.

However, if the company decides that they need to be alerted only once when a clinician leaves their designated zone since it is a permanent security issue, the system can be modified to send alerts only once per clinician area exit. This will simplify the script and reduce the number of GET requests that have to be made.

Additionally, it is possible that a clinician is on the edge of their bounding polygon, in which case simple GPS error can result in them being detected as moving in and out frequently. In such cases, capping the number of email alerts sent (to, say, 1 per minute or 5 minutes) can potentially reduce repetitive alerts. I have currently implemented this for the case where the endpoint doesn't return and we have JSON that does not indicate anything about location, but just an error. If the API is down for a long duration, not having a timeout of this sort would mean a lot of spam emails.

We can also implement additional features like daily reports on each clinician if this service is to stay live for long durations.

## Unit test results - email alerts

<img width="1112" alt="image" src="https://user-images.githubusercontent.com/34567765/166391427-af854af0-7846-4a69-9d63-1db665d95a28.png">

<img width="1109" alt="image" src="https://user-images.githubusercontent.com/34567765/166188630-be32ccb6-c70b-4446-8493-4037e21ddf60.png">

<img width="1111" alt="image" src="https://user-images.githubusercontent.com/34567765/166188746-1dead7ad-c949-416f-bea2-df5e72fdb78b.png">

