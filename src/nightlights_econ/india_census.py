"""India Census 2011 district populations by state (GAUL names).

Used to compute district/state population ratios for fair city selection
across states of very different sizes.

State totals are from Census 2011 final population tables.
District populations are 2011 Census primary census abstracts.
GAUL spellings used throughout (e.g. "Orissa" not "Odisha").
"""

from __future__ import annotations

# {gaul_state: {gaul_district: pop_2011}}
DISTRICT_POP: dict[str, dict[str, int]] = {
    "Andhra Pradesh": {  # includes undivided AP (Telangana not yet split in GAUL 2015)
        "Adilabad": 2737738, "Anantapur": 4083315, "Chittoor": 4174064,
        "Cuddapah": 2884524, "East Godavari": 5154296, "Guntur": 4889230,
        "Hyderabad": 3943323, "Karimnagar": 3811738, "Khammam": 2797741,
        "Krishna": 4529009, "Kurnool": 4046601, "Mahbubnagar": 4042191,
        "Medak": 3033288, "Nalgonda": 3489350, "Nellore": 2966082,
        "Nizamabad": 2551335, "Prakasam": 3397448, "Rangareddi": 5296396,
        "Srikakulam": 2703114, "Vishakhapatnam": 4288113, "Vizianagaram": 2342868,
        "Warangal": 3528220, "West Godavari": 3934782,
    },
    "Arunachal Pradesh": {
        "Changlang": 147951, "Dibang Valley": 7948, "East Kameng": 78690,
        "East Siang": 99019, "Kurung Kumey": 89717, "Lohit": 145726,
        "Lower Dibang Valley": 209390, "Lower Subansiri": 83030,
        "Papum Pare": 176353, "Tawang": 49977, "Tirap": 111997,
        "Upper Siang": 35289, "Upper Subansiri": 83021, "West Kameng": 87013,
        "West Siang": 112272,
    },
    "Assam": {
        "Barpeta": 1693190, "Bongaigaon": 738772, "Cachar": 1736617,
        "Chirang": 481818, "Darrang": 928500, "Dhemaji": 686133,
        "Dhubri": 1948632, "Dibrugarh": 1326335, "Dima Hasao": 213529,
        "Goalpara": 1008959, "Golaghat": 1058673, "Hailakandi": 659260,
        "Jorhat": 1091295, "Kamrup": 1513140, "Kamrup Metropolitan": 1260419,
        "Karbi Anglong": 956313, "Karimganj": 1228686, "Kokrajhar": 887142,
        "Lakhimpur": 1042137, "Morigaon": 957423, "Nagaon": 2826006,
        "Nalbari": 769919, "Sivasagar": 1151050, "Sonitpur": 1924110,
        "Tinsukia": 1327929, "Udalguri": 831668,
    },
    "Bihar": {
        "Araria": 2811569, "Arwal": 700843, "Aurangabad": 2511243,
        "Banka": 2029339, "Begusarai": 2970541, "Bhagalpur": 3037766,
        "Bhojpur": 2728407, "Buxar": 1706061, "Darbhanga": 3921971,
        "East Champaran": 5099371, "Gaya": 4391418, "Gopalganj": 2562012,
        "Jamui": 1756078, "Jehanabad": 1125313, "Kaimur": 1626384,
        "Katihar": 3071029, "Khagaria": 1666886, "Kishanganj": 1690400,
        "Lakhisarai": 1000912, "Madhepura": 2001762, "Madhubani": 4487379,
        "Munger": 1359054, "Muzaffarpur": 4801062, "Nalanda": 2877653,
        "Nawada": 2219146, "Patna": 5838465, "Purnia": 3264619,
        "Rohtas": 2962593, "Saharsa": 1897102, "Samastipur": 4261566,
        "Saran": 3951862, "Sheikhpura": 634927, "Sheohar": 656916,
        "Sitamarhi": 3423574, "Siwan": 3330464, "Supaul": 2228397,
        "Vaishali": 3495021, "West Champaran": 3935042,
    },
    "Chandigarh": {
        "Chandigarh": 1055450,
    },
    "Chhattisgarh": {
        "Bastar": 1413199, "Bijapur": 255180, "Bilaspur": 2663629,
        "Dantewada": 533638, "Dhamtari": 799781, "Durg": 3343872,
        "Janjgir-Champa": 1619707, "Jashpur": 851669, "Kanker": 748941,
        "Kawardha": 822526, "Korba": 1206640, "Koriya": 659366,
        "Mahasamund": 1032754, "Narayanpur": 139820, "Raigarh": 1493984,
        "Raipur": 4063872, "Rajnandgaon": 1537520, "Surajpur": 632320,
        "Surguja": 2361329,
    },
    "Dadra and Nagar Haveli": {
        "Dadra and Nagar Haveli": 343709,
    },
    "Daman and Diu": {
        "Daman": 191173, "Diu": 52074,
    },
    "Delhi": {
        "Central Delhi": 582320, "East Delhi": 1709346, "New Delhi": 142004,
        "North Delhi": 887978, "North East Delhi": 2165716,
        "North West Delhi": 3656521, "Shahdara": 1711396,
        "South Delhi": 2731929, "South East Delhi": 1707599,
        "South West Delhi": 2292958, "West Delhi": 2543243,
    },
    "Goa": {
        "North Goa": 818008, "South Goa": 640537,
    },
    "Gujarat": {
        "Ahmedabad": 7214225, "Amreli": 1514190, "Anand": 2090276,
        "Banaskantha": 3120673, "Bharuch": 1551019, "Bhavnagar": 2877961,
        "Dahod": 2127086, "Dang": 228291, "Gandhinagar": 1387478,
        "Jamnagar": 2160119, "Junagadh": 2743082, "Kheda": 2298934,
        "Kutch": 2092371, "Mahesana": 2027727, "Narmada": 590379,
        "Navsari": 1334023, "Panchmahal": 2390776, "Patan": 1343734,
        "Porbandar": 585449, "Rajkot": 3804558, "Sabarkantha": 2428553,
        "Surat": 6081322, "Surendranagar": 1756268, "Tapi": 807022,
        "Vadodara": 4157568, "Valsad": 1703068,
    },
    "Haryana": {
        "Ambala": 1136784, "Bhiwani": 1634440, "Faridabad": 1809733,
        "Fatehabad": 941522, "Gurgaon": 1514085, "Hisar": 1743931,
        "Jhajjar": 956907, "Jind": 1334152, "Kaithal": 1072861,
        "Karnal": 1505324, "Kurukshetra": 964655, "Mahendragarh": 921680,
        "Mewat": 1089263, "Palwal": 1042708, "Panchkula": 561293,
        "Panipat": 1202811, "Rewari": 900332, "Rohtak": 1058683,
        "Sirsa": 1295189, "Sonipat": 1450001, "Yamuna Nagar": 1214205,
    },
    "Himachal Pradesh": {
        "Bilaspur": 382056, "Chamba": 518844, "Hamirpur": 454293,
        "Kangra": 1510075, "Kinnaur": 84121, "Kullu": 437903,
        "Lahaul And Spiti": 31528, "Mandi": 999518, "Shimla": 814010,
        "Sirmaur": 530164, "Solan": 580320, "Una": 521057,
    },
    "Jharkhand": {
        "Bokaro": 2061918, "Chatra": 1042304, "Deoghar": 1492073,
        "Dhanbad": 2684487, "Dumka": 1321096, "East Singhbhum": 2291032,
        "Garhwa": 1322387, "Giridih": 2445203, "Godda": 1312587,
        "Gumla": 1025213, "Hazaribagh": 1734495, "Jamtara": 791042,
        "Khunti": 531885, "Koderma": 717169, "Latehar": 726677,
        "Lohardaga": 461790, "Pakur": 899200, "Palamu": 1936319,
        "Ramgarh": 949159, "Ranchi": 2914253, "Sahibganj": 1150567,
        "Seraikela Kharsawan": 1065056, "Simdega": 595447,
        "West Singhbhum": 1502338,
    },
    "Karnataka": {
        "Bagalkot": 1890826, "Bangalore Rural": 990923, "Bangalore Urban": 9621551,
        "Belgaum": 4779661, "Bellary": 2532383, "Bidar": 1700018,
        "Bijapur": 2175102, "Chamrajnagar": 1020962, "Chikmagalur": 1137574,
        "Chitradurga": 1659456, "Dakshin Kannad": 2083625, "Davanagere": 1946905,
        "Dharwad": 1847023, "Gadag": 1065235, "Gulbarga": 2564892,
        "Hassan": 1776221, "Haveri": 1598506, "Kodagu": 554762,
        "Kolar": 1540231, "Koppal": 1391292, "Mandya": 1805769,
        "Mysore": 3001127, "Raichur": 1928812, "Shimoga": 1752753,
        "Tumkur": 2678980, "Udupi": 1177908, "Uttar Kannand": 1436847,
    },
    "Kerala": {
        "Alappuzha": 2127789, "Ernakulam": 3282388, "Idukki": 1107453,
        "Kannur": 2523003, "Kasaragod": 1307375, "Kollam": 2635375,
        "Kottayam": 1979384, "Kozhikode": 3086293, "Malappuram": 4112920,
        "Palakkad": 2809934, "Pathanamthitta": 1197412, "Thiruvananthapuram": 3301427,
        "Thrissur": 3121200, "Wayanad": 816558,
    },
    "Madhya Pradesh": {
        "Agar Malwa": 571898, "Alirajpur": 728677, "Anuppur": 749237,
        "Ashoknagar": 845071, "Balaghat": 1701698, "Barwani": 1385659,
        "Betul": 1575362, "Bhind": 1703005, "Bhopal": 2371061,
        "Burhanpur": 757847, "Chhatarpur": 1762857, "Chhindwara": 2090306,
        "Damoh": 1264219, "Datia": 786754, "Dewas": 1563715,
        "Dhar": 2185793, "Dindori": 704218, "East Nimar": 1292042,
        "Guna": 1240938, "Gwalior": 2032036, "Harda": 570465,
        "Hoshangabad": 1241350, "Indore": 3276697, "Jabalpur": 2463289,
        "Jhabua": 1025048, "Katni": 1291684, "Mandla": 1054905,
        "Mandsaur": 1339832, "Morena": 1965137, "Narsinghpur": 1091854,
        "Neemuch": 825959, "Panna": 1016520, "Raisen": 1331597,
        "Rajgarh": 1546541, "Ratlam": 1455069, "Rewa": 2365106,
        "Sagar": 2378295, "Satna": 2228635, "Sehore": 1311082,
        "Seoni": 1379131, "Shahdol": 1066063, "Shajapur": 1512353,
        "Sheopur": 687615, "Shivpuri": 1726050, "Sidhi": 1127033,
        "Singrauli": 1178273, "Tikamgarh": 1445166, "Ujjain": 1986864,
        "Umaria": 644758, "Vidisha": 1458875, "West Nimar": 1385659,
    },
    "Maharashtra": {
        "Ahmadnagar": 4543159, "Akola": 1813906, "Amravati": 2887826,
        "Aurangabad": 3695928, "Beed": 2585049, "Bhandara": 1200334,
        "Buldhana": 2586258, "Chandrapur": 2204307, "Dhule": 2050862,
        "Gadchiroli": 1071795, "Gondia": 1322507, "Hingoli": 1177345,
        "Jalgaon": 4224442, "Jalna": 1958483, "Kolhapur": 3876001,
        "Latur": 2455543, "Mumbai City": 3085411, "Mumbai Suburban": 9332481,
        "Nagpur": 4653171, "Nanded": 3354847, "Nandurbar": 1648295,
        "Nashik": 6109052, "Osmanabad": 1657576, "Palghar": 2990116,
        "Parbhani": 1836086, "Pune": 9426959, "Raigad": 2635394,
        "Ratnagiri": 1615069, "Sangli": 2822143, "Satara": 3003922,
        "Sindhudurg": 849651, "Solapur": 4317756, "Thane": 11054131,
        "Wardha": 1296157, "Washim": 1198718, "Yavatmal": 2772348,
    },
    "Manipur": {
        "Bishnupur": 240363, "Chandel": 144028, "Churachandpur": 274143,
        "Imphal East": 456113, "Imphal West": 517992, "Senapati": 479148,
        "Tamenglong": 140143, "Thoubal": 422168, "Ukhrul": 183115,
    },
    "Meghalaya": {
        "East Garo Hills": 317917, "East Khasi Hills": 824059,
        "Jaintia Hills": 392523, "Ri Bhoi": 258380,
        "South Garo Hills": 142574, "West Garo Hills": 663398,
        "West Khasi Hills": 383461,
    },
    "Mizoram": {
        "Aizawl": 400309, "Champhai": 125745, "Kolasib": 83955,
        "Lawngtlai": 109860, "Lunglei": 154738, "Mamit": 86364,
        "Saiha": 56574, "Serchhip": 64937,
    },
    "Nagaland": {
        "Dimapur": 378811, "Kiphire": 74033, "Kohima": 270063,
        "Longleng": 50593, "Mokokchung": 194622, "Mon": 250260,
        "Peren": 95219, "Phek": 163418, "Tuensang": 196801,
        "Wokha": 166343, "Zunheboto": 143734,
    },
    "Orissa": {  # GAUL uses old name
        "Angul": 1271703, "Balangir": 1648574, "Baleshwar": 2317419,
        "Bargarh": 1478833, "Bhadrak": 1506522, "Boudh": 441162,
        "Cuttack": 2618708, "Deogarh": 312520, "Dhenkanal": 1192948,
        "Gajapati": 575880, "Ganjam": 3520151, "Jagatsinghapur": 1136604,
        "Jajapur": 1826275, "Jharsuguda": 579505, "Kalahandi": 1573686,
        "Kandhamal": 731952, "Kendrapara": 1440271, "Kendujhar": 1802777,
        "Khordha": 2246341, "Koraput": 1376934, "Malkangiri": 612727,
        "Mayurbhanj": 2513895, "Nabarangapur": 1218762, "Nayagarh": 962789,
        "Nuapada": 610382, "Puri": 1697983, "Rayagada": 961959,
        "Sambalpur": 1044410, "Sonapur": 652107, "Sundargarh": 2093437,
    },
    "Puducherry": {
        "Karaikal": 200222, "Mahe": 41816, "Pondicherry": 946600,
        "Yanam": 55616,
    },
    "Punjab": {
        "Amritsar": 2490891, "Barnala": 596294, "Bathinda": 1388859,
        "Faridkot": 617508, "Fatehgarh Sahib": 599814, "Fazilka": 1180786,
        "Ferozepur": 2026831, "Gurdaspur": 2299026, "Hoshiarpur": 1582793,
        "Jalandhar": 2193590, "Kapurthala": 817668, "Ludhiana": 3498739,
        "Mansa": 768808, "Moga": 992289, "Muktsar": 902702,
        "Nawanshahr": 614362, "Pathankot": 678708, "Patiala": 1895686,
        "Rup Nagar": 683349, "Sangrur": 1654408, "Sahibzada Ajit Singh Nagar": 986147,
        "Tarn Taran": 1120070,
    },
    "Rajasthan": {
        "Ajmer": 2584913, "Alwar": 3671999, "Banswara": 1798194,
        "Baran": 1223755, "Barmer": 2603953, "Bharatpur": 2549959,
        "Bhilwara": 2410459, "Bikaner": 2363937, "Bundi": 1113725,
        "Chittorgarh": 1544392, "Churu": 2041172, "Dausa": 1637226,
        "Dhaulpur": 1207293, "Dungarpur": 1388552, "Hanumangarh": 1779650,
        "Jaipur": 6626178, "Jaisalmer": 669919, "Jalor": 1828730,
        "Jhalawar": 1411327, "Jhunjhunu": 2139658, "Jodhpur": 3687165,
        "Karauli": 1458248, "Kota": 1951014, "Nagaur": 3307743,
        "Pali": 2037573, "Pratapgarh": 868231, "Rajsamand": 1158158,
        "Sawai Madhopur": 1338114, "Sikar": 2677333, "Sirohi": 1036346,
        "Sri Ganganagar": 1969520, "Tonk": 1421711, "Udaipur": 3068420,
    },
    "Sikkim": {
        "East Sikkim": 283583, "North Sikkim": 43354,
        "South Sikkim": 146850, "West Sikkim": 136435,
    },
    "Tamil Nadu": {
        "Ariyalur": 754894, "Chennai": 7088000, "Coimbatore": 3458045,
        "Cuddalore": 2605914, "Dharmapuri": 1506843, "Dindigul": 2159775,
        "Erode": 2251744, "Kancheepuram": 3998252, "Kanniyakumari": 1870374,
        "Karur": 1064493, "Madurai": 3038252, "Nagapattinam": 1616450,
        "Namakkal": 1726601, "Nilgiris": 735394, "Perambalur": 565223,
        "Pudukkottai": 1618345, "Ramanathapuram": 1353445, "Salem": 3482056,
        "Sivaganga": 1339101, "Thanjavur": 2405890, "Theni": 1245899,
        "Thiruvallur": 3728103, "Thoothukudi": 1750176,
        "Tiruchchirappalli": 2713858, "Tirunelveli Kattabo": 3077716,
        "Tiruvannamalai": 2464875, "Vellore": 3936331,
        "Villupuram": 3458873, "Virudhunagar": 1942288,
    },
    "Tripura": {
        "Dhalai": 378230, "Gomati": 443841, "Khowai": 321747,
        "North Tripura": 695071, "Sepahijala": 635581,
        "Sipahijala": 635581, "South Tripura": 430691,
        "Unakoti": 271199, "West Tripura": 1725739,
    },
    "Uttar Pradesh": {
        "Agra": 4418797, "Aligarh": 3673889, "Allahabad": 5954391,
        "Ambedkar Nagar": 2397888, "Amethi": 2387813, "Amroha": 1840221,
        "Auraiya": 1372287, "Azamgarh": 4613913, "Baghpat": 1303048,
        "Bahraich": 3487731, "Ballia": 3239774, "Balrampur": 2148665,
        "Banda": 1799541, "Barabanki": 3260699, "Bareilly": 4448359,
        "Basti": 2461056, "Bijnor": 3682713, "Budaun": 3712738,
        "Bulandshahr": 3499171, "Chandauli": 1952756, "Chitrakoot": 990626,
        "Deoria": 3100946, "Etah": 1774480, "Etawah": 1581810,
        "Faizabad": 2470996, "Farrukhabad": 1887577, "Fatehpur": 2632733,
        "Firozabad": 2498156, "Gautam Buddh Nagar": 1648115,
        "Ghaziabad": 4681645, "Ghazipur": 3620268, "Gonda": 3433919,
        "Gorakhpur": 4440895, "Hamirpur": 1104021, "Hapur": 1338211,
        "Hardoi": 4092845, "Hathras": 1564708, "Jalaun": 1689974,
        "Jaunpur": 4494204, "Jhansi": 2000755, "Kannauj": 1656616,
        "Kanpur Dehat": 1795092, "Kanpur Nagar": 4581268, "Kasganj": 1438166,
        "Kaushambi": 1599596, "Kheri": 4021243, "Kushinagar": 3564544,
        "Lalitpur": 1218002, "Lucknow": 4588455, "Maharajganj": 2684703,
        "Mahoba": 875958, "Mainpuri": 1868529, "Mathura": 2547184,
        "Mau": 2205968, "Meerut": 3443689, "Mirzapur": 2496970,
        "Moradabad": 4772006, "Muzaffarnagar": 4143512, "Pilibhit": 2031007,
        "Pratapgarh": 3209141, "Raebareli": 3404004, "Rampur": 2335398,
        "Saharanpur": 3466382, "Sambhal": 2171847, "Sant Kabir Nagar": 1715183,
        "Sant Ravidas Nagar": 1554203, "Shahjahanpur": 3002376,
        "Shamli": 1378453, "Shrawasti": 1117361, "Siddharthnagar": 2559297,
        "Sitapur": 4474446, "Sonbhadra": 1862559, "Sultanpur": 3797117,
        "Unnao": 3108953, "Varanasi": 3676841,
    },
    "Uttarakhand": {
        "Almora": 621927, "Bageshwar": 259840, "Chamoli": 391605,
        "Champawat": 259648, "Dehradun": 1696694, "Haridwar": 1890422,
        "Nainital": 954605, "Pauri Garhwal": 686527, "Pithoragarh": 483439,
        "Rudraprayag": 236857, "Tehri Garhwal": 617949, "Udham Singh Nagar": 1648902,
        "Uttarkashi": 330086,
    },
    "West Bengal": {
        "Bankura": 3596292, "Bardhaman": 7723663, "Birbhum": 3502404,
        "Cooch Behar": 2822780, "Dakshin Dinajpur": 1676276,
        "Darjeeling": 1846823, "Hooghly": 5520389, "Howrah": 4850029,
        "Jalpaiguri": 3872846, "Kolkata": 4496694, "Maldah": 3988845,
        "Murshidabad": 7103807, "Nadia": 5168488, "North 24 Parganas": 10009781,
        "Paschim Medinipur": 5913457, "Purba Medinipur": 5094238,
        "Purulia": 2930115, "South 24 Parganas": 8153176,
        "Uttar Dinajpur": 3007134,
    },
    "Andaman and Nicobar": {
        "Nicobar": 36842, "North and Middle Andaman": 105613,
        "South Andaman": 238142,
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Census 2001 district populations (for computing per-district growth rates)
# Source: Census of India 2001 primary census abstracts
# ─────────────────────────────────────────────────────────────────────────────
DISTRICT_POP_2001: dict[str, dict[str, int]] = {
    "Andhra Pradesh": {
        "Adilabad": 2483573, "Anantapur": 3641756, "Chittoor": 3735000,
        "Cuddapah": 2574580, "East Godavari": 4901420, "Guntur": 4465144,
        "Hyderabad": 3637483, "Karimnagar": 3493217, "Khammam": 2531477,
        "Krishna": 4187841, "Kurnool": 3530093, "Mahbubnagar": 3508985,
        "Medak": 2662296, "Nalgonda": 3228381, "Nellore": 2615898,
        "Nizamabad": 2345685, "Prakasam": 3059152, "Rangareddi": 3512856,
        "Srikakulam": 2538362, "Vishakhapatnam": 3789823, "Vizianagaram": 2244835,
        "Warangal": 3219879, "West Godavari": 3803044,
    },
    "Arunachal Pradesh": {
        "Changlang": 120850, "Lower Dibang Valley": 163047,
        "Papum Pare": 137680, "East Siang": 80455, "West Siang": 98940,
    },
    "Assam": {
        "Nagaon": 2314629, "Dhubri": 1634589, "Sonitpur": 1924110,
        "Kamrup": 1517792, "Barpeta": 1457685, "Cachar": 1443116,
        "Dibrugarh": 1176911, "Jorhat": 995922, "Lakhimpur": 909054,
        "Tinsukia": 1127205, "Darrang": 1504882,
    },
    "Bihar": {
        "Patna": 4709851, "East Champaran": 4027226, "Muzaffarpur": 3743130,
        "Gaya": 3736593, "Samastipur": 3448691, "Vaishali": 2894081,
    },
    "Chandigarh": {"Chandigarh": 900635},
    "Chhattisgarh": {
        "Raipur": 2864038, "Durg": 2773047, "Bilaspur": 2128886,
        "Surguja": 1987730, "Raigarh": 1269710, "Korba": 1002928,
    },
    "Delhi": {
        "North West Delhi": 2847395, "South Delhi": 2258327, "West Delhi": 2115000,
        "East Delhi": 1365000, "North East Delhi": 1648000, "South West Delhi": 1852000,
        "North Delhi": 765000, "Shahdara": 1100000,
    },
    "Goa": {"North Goa": 666930, "South Goa": 529978},
    "Gujarat": {
        "Ahmedabad": 5817827, "Surat": 4996391, "Vadodara": 3638209,
        "Rajkot": 3157676, "Jamnagar": 1913685, "Gandhinagar": 1138682,
        "Anand": 1856680, "Kheda": 2022876,
    },
    "Haryana": {
        "Faridabad": 1055501, "Hisar": 1486517, "Bhiwani": 1423480,
        "Gurgaon": 870539, "Karnal": 1274183, "Rohtak": 940915,
        "Ambala": 1003356, "Sonipat": 1279042,
    },
    "Himachal Pradesh": {
        "Kangra": 1339030, "Mandi": 900987, "Shimla": 721745,
        "Solan": 480567, "Kullu": 381571, "Una": 448273,
        "Hamirpur": 412491, "Bilaspur": 340751,
    },
    "Jharkhand": {
        "Ranchi": 2044666, "Dhanbad": 2065982, "Giridih": 2044934,
        "Bokaro": 1766001, "Hazaribagh": 1436604, "East Singhbhum": 2090069,
        "West Singhbhum": 1502338, "Palamu": 1646064,
    },
    "Karnataka": {
        "Bangalore Urban": 6537124, "Belgaum": 4214505, "Mysore": 2624911,
        "Gulbarga": 2152213, "Dharwad": 1604286, "Dakshin Kannad": 1897730,
        "Tumkur": 2584711, "Bellary": 2027518, "Bijapur": 1806918,
        "Bidar": 1465793, "Raichur": 1659414, "Davanagere": 1790321,
        "Shimoga": 1644294, "Hassan": 1630156,
    },
    "Kerala": {
        "Thiruvananthapuram": 3234356, "Ernakulam": 3105798, "Kozhikode": 2879131,
        "Malappuram": 3625471, "Thrissur": 2975440, "Kollam": 2584338,
        "Palakkad": 2617072, "Kannur": 2408956, "Alappuzha": 2109649,
        "Kottayam": 1953646, "Kasaragod": 1203342, "Wayanad": 786627,
        "Idukki": 1128605, "Pathanamthitta": 1231577,
    },
    "Madhya Pradesh": {
        "Indore": 2469891, "Jabalpur": 2192463, "Bhopal": 1825007,
        "Gwalior": 1690938, "Rewa": 2020348, "Sagar": 2065744,
    },
    "Maharashtra": {
        "Thane": 8128833, "Pune": 7232555, "Mumbai Suburban": 8587600,
        "Nashik": 4993796, "Nagpur": 4051444, "Aurangabad": 3200272,
        "Solapur": 3855826, "Kolhapur": 3523162, "Mumbai City": 3326837,
        "Ahmadnagar": 4005413, "Jalgaon": 3679936,
    },
    "Manipur": {
        "Imphal West": 444043, "Imphal East": 393780, "Bishnupur": 208073,
        "Thoubal": 366743, "Senapati": 394061, "Churachandpur": 227755,
        "Ukhrul": 157546, "Chandel": 117466,
    },
    "Meghalaya": {
        "East Khasi Hills": 660742, "West Garo Hills": 515203, "Jaintia Hills": 295692,
        "East Garo Hills": 239976, "West Khasi Hills": 294115,
    },
    "Mizoram": {
        "Aizawl": 309869, "Lunglei": 124048, "Champhai": 96945,
    },
    "Nagaland": {
        "Dimapur": 269218, "Kohima": 255462, "Mon": 216613,
        "Mokokchung": 174403, "Tuensang": 158454, "Wokha": 135376,
    },
    "Orissa": {
        "Ganjam": 3161751, "Cuttack": 2341877, "Mayurbhanj": 2296091,
        "Khordha": 1874405, "Baleshwar": 2138411, "Sundargarh": 1881444,
        "Sambalpur": 962694, "Koraput": 1177954, "Keonjhar": 1561371,
    },
    "Puducherry": {"Pondicherry": 855566, "Karaikal": 170791},
    "Punjab": {
        "Ludhiana": 3026988, "Amritsar": 2188566, "Gurdaspur": 2100000,
        "Jalandhar": 1954773, "Patiala": 1677013, "Bathinda": 1155827,
        "Sangrur": 1438085, "Hoshiarpur": 1439426,
    },
    "Rajasthan": {
        "Jaipur": 5251071, "Jodhpur": 3166469, "Alwar": 2992592,
        "Nagaur": 2888399, "Udaipur": 2633069, "Kota": 1568591,
    },
    "Sikkim": {
        "East Sikkim": 244706, "South Sikkim": 109578,
        "West Sikkim": 117491, "North Sikkim": 43354,
    },
    "Tamil Nadu": {
        "Chennai": 6560242, "Coimbatore": 2856954, "Madurai": 2560943,
        "Tiruchchirappalli": 2422083, "Salem": 2989632, "Kancheepuram": 3211644,
        "Tirunelveli Kattabo": 2804437, "Vellore": 3483595, "Erode": 1993403,
        "Thiruvallur": 2996400, "Villupuram": 3269623,
    },
    "Tripura": {
        "West Tripura": 1592382, "North Tripura": 616173,
        "Dhalai": 295476, "South Tripura": 369928,
    },
    "Uttar Pradesh": {
        "Allahabad": 4940923, "Moradabad": 3926215, "Azamgarh": 3944696,
        "Lucknow": 3647834, "Kanpur Nagar": 4138558, "Ghaziabad": 3290586,
        "Bareilly": 3597033, "Agra": 3620436, "Varanasi": 3138671,
        "Gorakhpur": 3850568, "Muzaffarnagar": 3544614,
    },
    "Uttarakhand": {
        "Haridwar": 1447187, "Dehradun": 1279083, "Udham Singh Nagar": 1235614,
        "Nainital": 762809, "Pauri Garhwal": 696770, "Almora": 630064,
    },
    "West Bengal": {
        "North 24 Parganas": 8924654, "South 24 Parganas": 6906869,
        "Bardhaman": 6895639, "Murshidabad": 5866569, "Nadia": 4604827,
        "Paschim Medinipur": 5218074, "Hooghly": 5048003, "Howrah": 4273099,
        "Kolkata": 4572876, "Purba Medinipur": 4567580, "Birbhum": 3061097,
        "Maldah": 3290468, "Jalpaiguri": 3398613,
    },
}

# State-level CAGR 2001→2011 from Census (for fallback when district 2001 data absent)
# Calculated as (2011_pop/2001_pop)^(1/10) - 1
STATE_CAGR_2001_2011: dict[str, float] = {
    "Andhra Pradesh": 0.0105, "Arunachal Pradesh": 0.0261, "Assam": 0.0162,
    "Bihar": 0.0228, "Chandigarh": 0.0159, "Chhattisgarh": 0.0209,
    "Dadra and Nagar Haveli": 0.0560, "Daman and Diu": 0.0531,
    "Delhi": 0.0192, "Goa": 0.0082, "Gujarat": 0.0188,
    "Haryana": 0.0193, "Himachal Pradesh": 0.0123, "Jharkhand": 0.0222,
    "Karnataka": 0.0155, "Kerala": 0.0047, "Madhya Pradesh": 0.0200,
    "Maharashtra": 0.0160, "Manipur": 0.0183, "Meghalaya": 0.0278,
    "Mizoram": 0.0231, "Nagaland": 0.0050, "Orissa": 0.0136,
    "Puducherry": 0.0106, "Punjab": 0.0138, "Rajasthan": 0.0213,
    "Sikkim": 0.0127, "Tamil Nadu": 0.0154, "Tripura": 0.0148,
    "Uttar Pradesh": 0.0185, "Uttarakhand": 0.0191, "West Bengal": 0.0138,
    "Andaman and Nicobar": 0.0076, "Lakshadweep": -0.0006,
}


def district_population_series(
    state: str,
    district: str,
    target_years: list[int],
) -> dict[int, float]:
    """Compute population for a district at each target year.

    Uses Census 2001 and 2011 data to compute a district-specific CAGR.
    Projects forward using that rate. Falls back to state-level CAGR if
    2001 district data is unavailable.

    Args:
        state: GAUL state name.
        district: GAUL district name.
        target_years: Years to estimate population for.

    Returns:
        Dict {year: population}.
    """
    from .utils import interpolate_population

    pop_2011 = DISTRICT_POP.get(state, {}).get(district)
    pop_2001 = DISTRICT_POP_2001.get(state, {}).get(district)

    if pop_2011 is None:
        pop_2011 = 500_000  # fallback

    if pop_2001 is not None and pop_2001 > 0:
        cagr = (pop_2011 / pop_2001) ** (1 / 10) - 1
        # Cap to sensible bounds: -1% to +5% per year
        cagr = max(-0.01, min(0.05, cagr))
    else:
        cagr = STATE_CAGR_2001_2011.get(state, 0.015)

    # Build a sparse series: 2001, 2011, then project to 2031
    known = {2011: float(pop_2011)}
    if pop_2001 is not None:
        known[2001] = float(pop_2001)

    # Extrapolate beyond 2011 assuming CAGR continues (conservative)
    for yr in range(2012, max(target_years) + 1):
        known[yr] = pop_2011 * ((1 + cagr) ** (yr - 2011))

    return interpolate_population(known, target_years)


def state_population(state: str) -> int:
    """Total 2011 Census population for a state."""
    return sum(DISTRICT_POP.get(state, {}).values())


def select_districts(
    state: str,
    threshold: float = 0.05,
    min_districts: int = 2,
    max_districts: int = 8,
) -> list[tuple[str, float]]:
    """Select districts above a population ratio threshold.

    For each state, returns districts where:
        district_pop / state_pop >= threshold

    Enforces min_districts (take top-N if fewer qualify) and max_districts.

    Args:
        state: GAUL state name.
        threshold: Minimum district/state population ratio (default 5%).
        min_districts: Always return at least this many (by population rank).
        max_districts: Cap at this many districts.

    Returns:
        List of (district_name, ratio) sorted by ratio descending.
    """
    districts = DISTRICT_POP.get(state, {})
    if not districts:
        return []

    state_pop = sum(districts.values())
    if state_pop == 0:
        return []

    ranked = sorted(districts.items(), key=lambda x: x[1], reverse=True)
    above = [(d, p / state_pop) for d, p in ranked if p / state_pop >= threshold]

    if len(above) < min_districts:
        above = [(d, p / state_pop) for d, p in ranked[:min_districts]]

    return above[:max_districts]


def all_states() -> list[str]:
    return sorted(DISTRICT_POP.keys())
