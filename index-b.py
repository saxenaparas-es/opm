#Import packages
import requests
import json
import pandas as pd 
import sys
import paho.mqtt.client as paho
from apscheduler.schedulers.background import BackgroundScheduler
from subprocess import Popen, PIPE
from datetime import datetime, timedelta
import os
import logging
import time
import platform
import re

version = platform.python_version().split(".")[0]
if version == "3":
	import app_config.app_config as cfg
	import timeseries.timeseries as ts
elif version == "2":
	import app_config as cfg
	import timeseries as ts

qr = ts.timeseriesquery()
unitId = ""
unitId = os.environ.get("UNIT_ID")
if unitId==None:
	print("no unit id passed exiting")
	exit()

def get_run_mode():

	if os.getenv("RUN_MODE"):
		return "cron"
	return "server"


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def setup_logging(run_mode):
	log_file = os.path.join(BASE_DIR, "cron.log")

	if run_mode == "cron":
		logging.basicConfig(
			filename=log_file,
			level=logging.INFO,
			format="%(asctime)s | %(levelname)s | %(message)s",
			encoding="utf-8"
		)
	else:
		logging.basicConfig(
			level=logging.INFO,
			format="%(levelname)s | %(message)s"
		)	



if not re.match(r'^[A-Za-z0-9_]+$', unitId):
	print(f"Invalid UNIT_ID '{unitId}'. Special characters are not allowed. Exiting.")
	exit()

SLEEP_IN_MINS_BEFORE_ANY_EXIT_FOR_DOCKER_SAFETY = 30

mapping = ""
# config = cfg.getconfig()[unitId]
config = {
	# "api": {
	# 	"meta": 'https://pulse.thermaxglobal.com/exactapi',
	# 	"query": 'https://pulse.thermaxglobal.com/kairosapi/api/v1/datapoints/query',
	# 	"datapoints": "https://pulse.thermaxglobal.com/kairosapi/api/v1/datapoints",
	# 	"efficiency":"https://pulse.thermaxglobal.com/efficiency/"
	# }
	"api": {
		"meta": 'https://data.exactspace.co/exactapi',
		"query": 'https://data.exactspace.co/exactdata/api/v1/datapoints/query',
		"datapoints": "https://data.exactspace.co/kairosapi/api/v1/datapoints",
		"efficiency":"https://data.exactspace.co/efficiency/"
	}
}

import requests
url = 'https://data.exactspace.co/login'
dd = {"email":"jason.d@exactspace.co","password":"7588J@sond1"}
token = requests.post(url, json=dd).json()["id"]
print (token)

headers={}
headers["authorization"] = "Bearer f{token}"
effURL = config['api']['efficiency']
# effURL = "http://192.168.1.35:5068/efficiency/"
topic_line = "u/" + unitId + "/"
scheduler = BackgroundScheduler()
mapping_file_url = config["api"]["meta"]+'/units/'+unitId+'/boilerStressProfiles?filter={"where":{"type":"efficiencyMapping"}}'
res = requests.get(mapping_file_url,headers=headers)
print("sample print statement for test")
if res.status_code == 200 and len(res.json())!=0:
	mapping_file = res.json()[0]
	mapping = mapping_file["output"]
	#print json.dumps(mapping, indent =4)
else:
	mapping = ""

if (mapping == "") or (unitId == ""):
	print ("sleeping for " + str(SLEEP_IN_MINS_BEFORE_ANY_EXIT_FOR_DOCKER_SAFETY) + " minutes before exiting due to mapping file not found")
	time.sleep(SLEEP_IN_MINS_BEFORE_ANY_EXIT_FOR_DOCKER_SAFETY * 60)
	exit()




metricQueryTemplateName = str(unitId)


metricQueryTemplate = {
	"name" : metricQueryTemplateName,
	"datapoints" : [],
	"tags" : {
	"dataTagId" : "",
	"parameter" : "",
	"measureUnit" : "",
	"calculationType" : "", 
	"impact":0,
	}
}

def get_dataTagId_from_meta(unitId, meta_query_dict):
	url_meta = config["api"]["meta"]+'/units/'+unitId+'/tagmeta?filter={"where":'+json.dumps(meta_query_dict)+'}'
	print (url_meta)
	response = requests.get(url_meta)
	if response.status_code == 200:
		meta = json.loads(response.content)
		return meta[0]["dataTagId"]
	else:
		print ("error in fetchign dataTagId for a query, ", meta_query_dict, " from ", unitId)
		return "-"

def make_config_for_query_metric(unitId):
	urlAsset = config["api"]["meta"]+'/units/'+unitId+'/performanceApis?filter={"where":{"type":"assetTest"}}'
	response = requests.get(urlAsset)
	if response.status_code == 200:
		responseContent = json.loads(response.content)
		assetManagerConfig = {}
		for params in responseContent:
			if params["input"]["systemName"] in list(assetManagerConfig.keys()):
				if "dataTagId" in params["input"]["parameter"][0]["query"][0]:
					assetManagerConfig[params["input"]["systemName"]][params["input"]["parameter"][0]["query"][0]["dataTagId"]] = params["input"]["parameter"][0]["name"]
				else:
					dataTagId = get_dataTagId_from_meta(unitId, params["input"]["parameter"][0]["query"][0])
					assetManagerConfig[params["input"]["systemName"]][dataTagId] = params["input"]["parameter"][0]["name"]
			else:
				assetManagerConfig[params["input"]["systemName"]] = {}
				if "dataTagId" in params["input"]["parameter"][0]["query"][0]:
					# print (params["input"]["systemName"])
					# print (assetManagerConfig)
					assetManagerConfig[params["input"]["systemName"]][params["input"]["parameter"][0]["query"][0]["dataTagId"]] = params["input"]["parameter"][0]["name"]
				else:
					dataTagId = get_dataTagId_from_meta(unitId, params["input"]["parameter"][0]["query"][0])
					assetManagerConfig[params["input"]["systemName"]][dataTagId] = params["input"]["parameter"][0]["name"]

		return assetManagerConfig
	else:
		print (response.status_code)
		print ("Some error in fetching asset manager config details from url")
		return {}


assetManagerConfig = make_config_for_query_metric(unitId)
print (assetManagerConfig)

def on_connect(client, userdata, flags, rc):
	print ("Connected!")

def on_log(client, userdata, obj, buff):
	placeholder = 123
	# print ("log:" + str(buff))

port = os.environ.get("Q_PORT")
if not port:
	port = 1883
else:
	port = int(port)
print ("Running port", port)

client = paho.Client()
client.on_log = on_log
client.on_connect = on_connect
client.loop_start()
# Used for Thermax
try:
	client.username_pw_set(username=config["BROKER_USERNAME"], password=config["BROKER_PASSWORD"])
except:
	pass
client.connect(config['BROKER_ADDRESS'], port, 120)

def getThreshold(dataTagId):
	tagmeta=config["api"]["meta"]+'/tagmeta?filter={"where":{"dataTagId":"'+str(dataTagId)+'"},"fields": "equipmentId"}'
	response = requests.get(tagmeta)
	tagBody = json.loads(response.content) 
	eqpUrl=config["api"]["meta"]+'/equipment?filter={"where":{"id":"'+tagBody[0]["equipmentId"]+'"},"fields": "value"}'
	response = requests.get(eqpUrl)
	value = json.loads(response.content)
	
#     print(value[0]["value"]) 
	
	return value[0]["value"]


def getLastValue(tag):
	qr.addMetrics(tag)
	qr.chooseTimeType("relative",{"start_value":1, "start_unit":"years"})
	qr.addAggregators([{"name":"last", "sampling_value":2,"sampling_unit":"years"}])
	qr.submitQuery()
	qr.formatResultAsDF()
	# print(qr.resultset["results"])
	if (len(qr.resultset["results"]) > 0):
		res=qr.resultset
		df = pd.DataFrame([{"time":res["queries"][0]["results"][0]["values"][0][0]}])
		for tag in res["queries"]:
			try:
				if df.iloc[0,0] <  tag["results"][0]["values"][0][0]:
					df.iloc[0,0] =  tag["results"][0]["values"][0][0]
				df.loc[0,tag["results"][0]["name"]] = tag["results"][0]["values"][0][1]
			except Exception as e:
				print("exception in query",e)
				print (tag, "error")
				pass
		return df
	else:
		print("no datapoints found in kairos")
		return pd.DataFrame()

def getLastValues(taglist,end_absolute=0):
	print (taglist)
	endTime = int((time.time()*1000) + (5.5*60*60*1000))
	ONE_MONTH_MS = 30 * 24 * 60 * 60 * 1000 
	startTime = endTime - ONE_MONTH_MS
	if end_absolute !=0:
		query = {"metrics": [],"start_absolute": startTime, "end_absolute":endTime }
	else:
		query = {"metrics": [],"start_absolute":startTime,"end_absolute":endTime}
	for tag in taglist:
		query["metrics"].append({"tags": {"type": ["raw","form","derived"]},"name": tag,"order":"desc","limit":1})
	# print (query)
	try:
		res = requests.post(config['api']['query'],json=query).json()
		# print (res)
		df = pd.DataFrame([{"time":res["queries"][0]["results"][0]["values"][0][0]}])
		for tag in res["queries"]:
			try:
				if df.iloc[0,0] <  tag["results"][0]["values"][0][0]:
					df.iloc[0,0] =  tag["results"][0]["values"][0][0]
				df.loc[0,tag["results"][0]["name"]] = tag["results"][0]["values"][0][1]
			except:
				print (tag, "error")
				pass
	
	except Exception as e:
		print(e)
		return pd.DataFrame()
	return df


def applyUltimateConfig(data, fuel, fuelConfig):
	if fuelConfig["mixtureType"]=="dynamic":
		data[fuelConfig["fuelFlow"]]=data[fuelConfig["fuelFlow"]].clip(lower=0)
		totalFuelFlow = data[fuelConfig["fuelFlow"]].sum(axis=1).values[0]
		#print "totalFuelFlow: ", totalFuelFlow
		#print "Fuel 1 flow: ", data[fuelConfig["fuelFlow"][0]].values[0]
		#print "Fuel 2 flow: ", data[fuelConfig["fuelFlow"][1]].values[0]
		for i, j in fuel.items():
			fuelItem = 0
			for index, tag in enumerate(j):
				#print "This: ", data[fuelConfig["fuelFlow"][index]].values[0], data[tag].values[0]
				fuelItem += ((data[fuelConfig["fuelFlow"][index]].values[0] * data[tag].values[0]) / totalFuelFlow)
			data[i] = fuelItem
		data["coalFlow"] = totalFuelFlow
		
	elif fuelConfig["mixtureType"]=="static":
		print("mixture type is static")
		setFlag=0
		for i , j in fuel.items():
			fuelItem=0
			for index, tag in enumerate(j):
				fuelItem += data[tag].sum()
				if "landingCost"  in  i:
					if (data[tag] == 0).any():
						print("landing cost of one of the tag is 0")
						setFlag=1
			if setFlag ==1 :
				data[i] = fuelItem
			else:
				data[i] = fuelItem / len(j)
		
	else:
		pass
	
	#print "^" * 20
	#print data.columns
	#print "^" * 20
	return data
	
	
def getUltimateData(fuelUltimate, loi, blr):	
	if blr.get("fuelUltimateConfig"):
		tags = []	
		for i, j in fuelUltimate.items():	
			if len(j) > 1:	
				tags.extend([str(k) for k in j])	
			else:	
				tags.append(str(j[0]))		
					
				
		for i, j in loi.items():		
			if len(j) > 1:	
				tags.extend([str(k) for k in j])	
			else:	
				tags.append(str(j[0]))		
					
		DYN_FUEL_FLAG = 0
		if blr.get("fuelUltimateConfig"):	
			if blr["fuelUltimateConfig"]["mixtureType"]=="dynamic":	
				tags.extend(blr["fuelUltimateConfig"]["fuelFlow"])
				DYN_FUEL_FLAG = 1	
					
		data = getLastValues(tags)
		# if data.empty:
		# 	data = getLastValue(tags)		
		# #print "%" * 20

		if (DYN_FUEL_FLAG == 1):
			CURR_TIME = int(time.time() * 1000 // 60000 * 60000)
			LAST_KNOWN_TS = data["time"][0]
			LAST_KNOWN_TS = LAST_KNOWN_TS
			print (CURR_TIME)
			print (LAST_KNOWN_TS)
			fuelTimeDiff = CURR_TIME - LAST_KNOWN_TS
			fuelTimeDiff_mins = fuelTimeDiff//60000

			if (fuelTimeDiff_mins >= 15):
				print ("Last Known Values for hourly fuel tags are more than 15 mins old")
				try:
					process = Popen(['python', os.environ['PWD'] + '/batch_calc_hourly_params_TBWES.py', str(unitId)],\
									stdout = PIPE, stderr = PIPE)
					stdout, stderr = process.communicate()
					print (stdout)
					# print stderr
				except Exception as e:
					print ("Popen Exception\n")
					print (e)

		data = applyUltimateConfig(data, fuelUltimate, blr["fuelUltimateConfig"])	
		data = applyUltimateConfig(data, loi, blr["fuelUltimateConfig"])	
		data.drop(tags, axis=1, inplace=True)	
		#print "AllTags: ", tags	
			
		#print data.columns	
		#print "%" * 20	
		return data
	else:
		tags, loi_tags, names = [], [], {}	
		for i, j in fuelUltimate.items():	
			tags.append(str(j[0]))	
			names[str(j[0])] = str(i)	
		for i, j in loi.items():	
			tags.append(str(j[0]))	
			loi_tags.append(str(j[0]))	
			names[str(j[0])] = str(i)	
		data = getLastValues(tags)	
		if (data.shape[1] != 0):	
			data.rename(columns=names, inplace=True)	
		else:	
			data = pd.DataFrame()	
			data["time"] = [0]	
			for i, j in fuelUltimate.items():	
				data[i] = j	
				
			for i, j in loi.items():	
				data[i] = j	
				 
		return data
	
	
def getProximateData(fuelProximate,loi,blr):
	tags, names, count1, count2, var_name, propLen, loi_tags = [], {}, 0, 0, 'var', 1, []
	for i,j in fuelProximate.items():
		if len(j)==2:
			propLen = 2
			tags.extend([str(k) for k in j])
			names[var_name + str(count1)] = str(i)
			count1 += 1
		else:
			tags.append(str(j[0]))
			names[str(j[0])] = str(i)

	for i,j in loi.items():
		tags.append(str(j[0]))
		loi_tags.append(str(j[0]))
		names[str(j[0])] = str(i)
		
	data =  getLastValues(tags)
	if (data.shape[1]!=0):
		for i, j in fuelProximate.items():
			if len(j)==2:
				data[var_name + str(count2)] = (data[j[0]] * blr["coalMixtureRatio"]["Q1"]  + data[j[1]] * blr["coalMixtureRatio"]["Q2"]) / 2
				count2 += 1
		
		data = data[[var_name + str(k) for k in range(len(fuelProximate))] + ["time"] + loi_tags] if (propLen != 1) else data
		data.rename(columns=names, inplace=True)
	else:
		data = pd.DataFrame()
		data["time"] = [0]
		for i, j in fuelProximate.items():
			data[i] = j
		for i,j in loi.items():
			data[i] = j

	return data


def getProximateDataOld(fuelProximate,loi):
	#tags = [fuelProximate["coalFC"][0],fuelProximate["coalVM"][0],fuelProximate["coalAsh"][0],fuelProximate["coalMoist"][0],fuelProximate["coalGCV"],loi["bedAshUnburntCarbon"][0],loi["flyAshUnburntCarbon"][0]]
	tags = [fuelProximate["coalFC"][0],fuelProximate["coalVM"][0],fuelProximate["coalAsh"][0],fuelProximate["coalMoist"][0],fuelProximate["coalGCV"]]
	
	names = {}
	names[fuelProximate["coalFC"][0]]="coalFC"
	names[fuelProximate["coalVM"][0]]="coalVM"
	names[fuelProximate["coalAsh"][0]]="coalAsh"
	names[fuelProximate["coalMoist"][0]]="coalMoist"
	names[fuelProximate["coalGCV"][0]]="coalGCV"
	#names[loi["bedAshUnburntCarbon"][0]]="bedAshUnburntCarbon"
	#names[loi["flyAshUnburntCarbon"][0]]="flyAshUnburntCarbon"
	for i,j in loi.items():
		tags.append(str(j[0]))
		names[str(j[0])] = str(i)

	data =  getLastValues(tags)
	if (data.shape[1]!=0):
		data.rename(columns=names, inplace=True)
	return data


def getTurbineRealtimeData(realtime):
	'''
	tags = [realtime["steamFlowMS"][0],realtime["steamPressureMS"][0],realtime["steamTempMS"][0],realtime["FWFinalTemp"][0],realtime["FWFinalPress"],realtime["load"]]
	names = {}
	names[realtime["load"][0]]="load"
	names[realtime["steamFlowMS"][0]]="steamFlowMS"
	names[realtime["steamPressureMS"][0]]="steamPressureMS"
	names[realtime["steamTempMS"][0]]="steamTempMS"
	names[realtime["FWFinalTemp"][0]]="FWFinalTemp"
	names[realtime["FWFinalPress"][0]]="FWFinalPress"
	'''
	tags, names, flag = [], {}, 0
	for i,j in realtime.items():
		if len(j) > 1:
			print (j[0], j[1])
			tags.append(j[0])
			tags.append(j[1])
			names[j[0]] = str(i) + "$1"
			names[j[1]] = str(i) + "$2"
			flag = 1
		else:
			tags.append(j[0])
			names[j[0]] = str(i)

	data = getLastValues(tags)
	# print (data.head())
	# print (names)

	if (data.shape[1]!=0):
		if (flag==0):
			data.rename(columns=names, inplace=True)
		else:
			data.rename(columns=names, inplace=True)
			for i,j in realtime.items():
				if len(j) > 1:
					# if ((data.iloc[0][str(i) + "$1"] > j[0]) and (data.iloc[0][str(i) + "$2"] > j[1])):
					data[str(i)] = (0.5 * (data[str(i) + "$1"] + data[str(i) + "$2"]))
					# else:
						# data[str(i)] = data[[str(i) + "$1", str(i) + "$2"]].max(axis=1)
					
					#print data.columns
					data.drop(columns=[str(i) + "$1", str(i) + "$2"], axis=1, inplace=True)
		
	return data


def getBoilerRealtimeDataOld(realtime):
	tags = [realtime["ambientAirTemp"][0],realtime["aphFlueGasOutletO2"][0],realtime["aphFlueGasOutletTemp"][0],realtime["boilerSteamFlow"][0],realtime["bedAshTemp"]]
	names = {}
	names[realtime["ambientAirTemp"][0]]="ambientAirTemp"
	names[realtime["aphFlueGasOutletO2"][0]]="aphFlueGasOutletO2"
	names[realtime["aphFlueGasOutletTemp"][0]]="aphFlueGasOutletTemp"
	names[realtime["boilerSteamFlow"][0]]="boilerSteamFlow"
	names[realtime["bedAshTemp"][0]]="bedAshTemp"

	data =  getLastValues(tags)
	if (data.shape[1]!=0):
		data.rename(columns=names, inplace=True)
	return data


def getBoilerRealtimeData(realtime):
	tags, names = [], {}
	for i, j in realtime.items():
		tags.append(str(j[0]))
		names[str(j[0])] = str(i)
	data = getLastValues(tags)
	if (data.shape[1]!=0):
		data.rename(columns=names, inplace=True)
	return data

# def generate_query_based_body(original_body):

def post_query_method(entire_input_output_combo_actual, entire_input_output_combo_design, entire_input_output_combo_bperf, assetManagerConfig, boiler_config, post_time):
	combos = [entire_input_output_combo_actual, entire_input_output_combo_design, entire_input_output_combo_bperf]
	# print (json.dumps(entire_input_output_combo_actual, indent=4))
	calc_type = ["actual", "design", "bperf"]
	for combo in combos:
		for k,v in combo["relationship"].items():
			# print (k,v)
			relatedTo = []
			for v2 in v:
				relatedTo.append(assetManagerConfig[boiler_config["systemName"]][boiler_config["outputs"][v2]])
			metricName = str(unitId) + "_" + boiler_config["systemName"] + "_asset_manager"
			tagsDict = {}
			tagsDict["dataTagId"] = "-"
			tagsDict["parameter"] = k
			tagsDict["measureUnit"] = "-"
			tagsDict["calculationType"] = calc_type[combos.index(combo)]
			tagsDict["relatedTo"] = json.dumps(relatedTo)
			# print (tagsDict)
			body_to_post = [{"name" : metricName, "datapoints" : [[post_time, round(combo.get(k), 3)]], "tags": tagsDict}]
			# print(body_to_post)
			qr.postDataPacket(body_to_post)
			# return query_body_publish1


def main():
	exec_start_time = time.time()
	mapping_file_url = config["api"]["meta"]+'/units/'+unitId+'/boilerStressProfiles?filter={"where":{"type":"efficiencyMapping"}}'
	res = requests.get(mapping_file_url)

	if res.status_code == 200 and len(res.json())!=0:
		mapping_file = res.json()[0]
		mapping = mapping_file["output"]
		# print (json.dumps(mapping, indent =4))

	if (mapping == "") or (unitId == ""):
		sys.exit("Unable to find mapping file")

	topic_line = "u/" + unitId + "/"
	post_time = int(time.time() * 1000 // 60000 * 60000)
	# """
	if mapping.get("turbineHeatRate"):
		for turbine in mapping["turbineHeatRate"]:    
			skip_flag=0
			Threshold_tags=[]
			Threshold_names={}
			#checks if boiler is down so that interconnection to turbine can be done 
			stateTag = turbine.get("equipmentStatus") if "equipmentStatus" in turbine else None
			if stateTag:
				print("equipment status tag is present ")
				stateTagValue=getLastValues([stateTag],end_absolute=0)
				stateTagValue=stateTagValue.iloc[-1,-1]
				print("statetagvalue")
				print(stateTagValue)
				if stateTagValue ==0:
					newdict = {}
					for turbine_inner in mapping["turbineHeatRate"]:
						if stateTag not in turbine_inner.get("equipmentStatus", []):
							stateTagValue=getLastValues([turbine_inner["equipmentStatus"]],end_absolute=0)
							stateTagValue=stateTagValue.iloc[-1,-1]
							if stateTagValue == 1:
								newdict={"FWFinalTemp":turbine_inner["realtime"]["FWFinalTemp"],"FWFinalPress":turbine_inner["realtime"]["FWFinalPress"]}
								break
							continue
					turbine["realtime"].update(newdict)

			if len(turbine["realtime"]) > 0 :
				realtimeData = getTurbineRealtimeData(turbine["realtime"])
				try :
					print("in try")
					for i,j in turbine["Threshold"].items():
						Threshold_tags.append(str(j[0]))

						Threshold_names[j[0]] = str(i)

					threshold = getLastValues(Threshold_tags)
					threshold.rename(columns=Threshold_names, inplace=True)
					threshold = threshold.to_dict(orient="records")[0]
					print(threshold)
				except Exception as e:
					threshold = 0    
					print("ignore the exception passing it since no threshold entered in manual page ")

				print("realtimeData")
				print(realtimeData)
				realtimeData = realtimeData.to_dict(orient="records")[0]
				if threshold:
						print("contains thresholds in dataEntry page")
						if realtimeData["load"] < threshold["load"] or realtimeData["steamFlowMS"]<threshold["steamFlowMS"]:
								skip_flag=1
				else:
						try: 
								if realtimeData["load"] < 1 or realtimeData["steamFlowMS"]<10:
										skip_flag  = 1
					#elif realtimeData["steamTempMS"] < 50 or  realtimeData["FWFinalTemp"] < 50 :
					 #   print("*****")
					  #  skip_flag  = 1
					#elif realtimeData["steamPressureMS"] < 10 or  realtimeData["FWFinalPress"] < 4 :
						#skip_flag  = 1
						except Exception as e:
								print("cogent3 tubine")
								if realtimeData["load"] < 0.5:
										skip_flag  = 1

				
				print ("TurbineRealtime data for thr calculation")
				print (json.dumps(realtimeData, indent=4))
				if mapping.get("plantHeatRate"):
						 
						mapping["plantHeatRate"]["design"] = {
								"turbineHeatRate": [],
								"boilerEfficiency": [],
								"boilerSteamFlow": [],
								"turbineSteamFlow": []
								}

						mapping["plantHeatRate"]["bestAchieved"] = {
								"turbineHeatRate": [],
								"boilerEfficiency": [],
								"boilerSteamFlow": [],
								"turbineSteamFlow": []
								}
				if skip_flag==0:

					realtimeDesignData = requests.post(effURL+"design",json={"realtime":turbine["realtime"],"loi":{},"load":realtimeData["load"],"loadTag":turbine["realtime"]["load"][0],"realtimeData":realtimeData,"unitId":unitId})
					if realtimeDesignData.status_code ==200:
						realtimeDesignData = json.loads(realtimeDesignData.content)

					realtimeBPData = requests.post(effURL+"bestachieved",json={"realtime":turbine["realtime"],"load":realtimeData["load"],"loadTag":turbine["realtime"]["load"][0],"realtimeData":realtimeData,"unitId":unitId})
					if realtimeBPData.status_code ==200:
						realtimeBPData = json.loads(realtimeBPData.content)
						for i,j in realtimeBPData.items():
							if j!=j :
								print (realtimeBPData[i])
								print (realtimeData[i])
								realtimeBPData[i] = realtimeData[i]
					#print("realtimeData",realtimeData)
					#print("realtimeBPData",realtimeBPData)
					#print("realtimeDesignData",realtimeDesignData)

					try:
						realtimeData["category"] = turbine.get("category")
						realtimeDesignData["category"] = turbine.get("category")
						realtimeBPData["category"] = turbine.get("category")
					except:
						pass

					# print("realtimeData",json.dumps(realtimeData))
					# print("realtimeBPData",json.dumps(realtimeBPData))
					print("realtimeDesignData",json.dumps(realtimeDesignData))
					if "MakeUpWaterFlow" in realtimeDesignData and realtimeDesignData["MakeUpWaterFlow"] != realtimeDesignData["MakeUpWaterFlow"]:
						realtimeDesignData["MakeUpWaterFlow"] = 0.0
						
					#sys.exit()
					try:
						for k,v in turbine["constants"].items():
							realtimeData[k] = v
							realtimeDesignData[k] = v
							realtimeBPData[k] = v
					except:
						pass
					
					thr = requests.post(effURL+"thr",json=realtimeData)
					if thr.status_code ==200:
						thr = json.loads(thr.content)
					else:
						thr = {"turbineHeatRate":0.1}
					thrDesign = requests.post(effURL+"thr",json=realtimeDesignData)
					if thrDesign.status_code ==200:
						thrDesign = json.loads(thrDesign.content)
					else:
						thrDesign = {"turbineHeatRate":0.1}
					thrBP = requests.post(effURL+"thr",json=realtimeBPData)
					if thrBP.status_code ==200:
						thrBP = json.loads(thrBP.content)
					else:
						thrBP = {"turbineHeatRate":0.1}
					# print("thr after calculation")
					# print (thr)
					try:
						print("in try of checking threshold")
						if isinstance(threshold, dict) and "turbineHeatRate" in threshold :
							thr["turbineHeatRate"] = max(800, min(thr["turbineHeatRate"], threshold["turbineHeatRate"]))
						else:
							print("no threshold tag considering by default 5000")
							thr["turbineHeatRate"] = max(800, min(thr["turbineHeatRate"],5000))

						# thr["turbineHeatRate"] = max(1500, min(thr["turbineHeatRate"], threshold["turbineHeatRate"] if threshold.get("turbineHeatRate") else 5000))
						print("thr in try",thr["turbineHeatRate"])
					except Exception as e:
						print (e )
						print ("\nSome error in calculating THR so makign it zero\n")
						thr["turbineHeatRate"] = 0.0
					# print(json.dumps(thr,indent=4))
					# print("thrDesign",json.dumps(thrDesign,indent=4))
					#print("thrBP",thrBP)
					# turbineDesign,turbineBperf= [],[]
					
					# print("mappingfile")
					# print(json.dumps(mapping,indent=4))
					if mapping.get("plantHeatRate"):
						mapping["plantHeatRate"]["realtime"]["turbineHeatRate"].append(thr["turbineHeatRate"])
						mapping["plantHeatRate"]["realtime"]["turbineSteamFlow"].append(realtimeData["steamFlowMS"])
						mapping["plantHeatRate"]["design"]["turbineHeatRate"].append(thrDesign["turbineHeatRate"])
						mapping["plantHeatRate"]["design"]["turbineSteamFlow"].append(realtimeDesignData["steamFlowMS"])
						mapping["plantHeatRate"]["bestAchieved"]["turbineHeatRate"].append(thrBP["turbineHeatRate"])
						mapping["plantHeatRate"]["bestAchieved"]["turbineSteamFlow"].append(realtimeBPData["steamFlowMS"])
						

					# Post value here
					for k,v in turbine["outputs"].items():
						body_publish1 = [{"name" : turbine["outputs"][k], "datapoints" : [[post_time, round(thr[k], 3)]], "tags" : {"type": "heat_rate_hourly"}}]
						body_publish2 = [{"name" : turbine["outputs"][k] + "_des", "datapoints" : [[post_time, round(thrDesign[k], 3)]], "tags" : {"type": "heat_rate_hourly"}}]
						body_publish3 = [{"name" : turbine["outputs"][k] + "_bperf", "datapoints" : [[post_time, round(thrBP[k], 3)]], "tags" : {"type": "heat_rate_hourly"}}]
					
						# Publish results to topics
						client.publish(topic_line + turbine["outputs"][k] + '/r', json.dumps([{"r": body_publish1[0]["datapoints"][0][1], "t": body_publish1[0]["datapoints"][0][0]}]))
						client.publish(topic_line + turbine["outputs"][k] + "_des" + '/r', json.dumps([{"r": body_publish2[0]["datapoints"][0][1], "t": body_publish2[0]["datapoints"][0][0]}]))
						client.publish(topic_line + turbine["outputs"][k] + "_bperf" + '/r', json.dumps([{"r": body_publish3[0]["datapoints"][0][1], "t": body_publish3[0]["datapoints"][0][0]}]))
					
						#print body_publish1
						#print body_publish2
						#print body_publish3
						client.publish("kairoswriteexternal",json.dumps(body_publish1))
						client.publish("kairoswriteexternal",json.dumps(body_publish2))
						client.publish("kairoswriteexternal",json.dumps(body_publish3))
						res1 = qr.postDataPacket(body_publish1)
						res2 = qr.postDataPacket(body_publish2)
						res3 = qr.postDataPacket(body_publish3)
					

					rawPublish = {}
					rawPublish["r"] = round(thr["turbineHeatRate"], 3)
					rawPublish["t"] = post_time
					#print rawPublish
					topic_line = "u/" + unitId + "/"
					#print topic_line+turbine["outputs"]["turbineHeatRate"]
					client.publish(topic_line+turbine["outputs"]["turbineHeatRate"], json.dumps([rawPublish]))
					
					
				else:
					if mapping.get("plantHeatRate"):
					#print("Skipping turbine",turbine["systemInstance"])
						mapping["plantHeatRate"]["realtime"]["turbineHeatRate"].append(0)
						mapping["plantHeatRate"]["realtime"]["turbineSteamFlow"].append(0)
						mapping["plantHeatRate"]["design"]["turbineHeatRate"].append(0)
						mapping["plantHeatRate"]["design"]["turbineSteamFlow"].append(0)
						mapping["plantHeatRate"]["bestAchieved"]["turbineHeatRate"].append(0)
						mapping["plantHeatRate"]["bestAchieved"]["turbineSteamFlow"].append(0)
					# Post value here
					body_publish1 = [{"name" : turbine["outputs"]["turbineHeatRate"], "datapoints" : [[post_time, 0]], "tags" : {"type": "heat_rate_hourly"}}]
					body_publish2 = [{"name" : turbine["outputs"]["turbineHeatRate"] + "_des", "datapoints" : [[post_time, 0]], "tags" : {"type": "heat_rate_hourly"}}]
					body_publish3 = [{"name" : turbine["outputs"]["turbineHeatRate"] + "_bperf", "datapoints" : [[post_time, 0]], "tags" : {"type": "heat_rate_hourly"}}]
					
					# Publish results to topics
					client.publish(topic_line + turbine["outputs"]["turbineHeatRate"] + '/r', json.dumps([{"r": body_publish1[0]["datapoints"][0][1], "t": body_publish1[0]["datapoints"][0][0]}]))
					client.publish(topic_line + turbine["outputs"]["turbineHeatRate"] + "_des" + '/r', json.dumps([{"r": body_publish2[0]["datapoints"][0][1], "t": body_publish2[0]["datapoints"][0][0]}]))
					client.publish(topic_line + turbine["outputs"]["turbineHeatRate"] + "_bperf" + '/r', json.dumps([{"r": body_publish3[0]["datapoints"][0][1], "t": body_publish3[0]["datapoints"][0][0]}]))
					
					#print body_publish1
					#print body_publish2
					#print body_publish3
					client.publish("kairoswriteexternal",json.dumps(body_publish1))
					client.publish("kairoswriteexternal",json.dumps(body_publish2))
					client.publish("kairoswriteexternal",json.dumps(body_publish3))
					res1 = qr.postDataPacket(body_publish1)
					res2 = qr.postDataPacket(body_publish2)
					res3 = qr.postDataPacket(body_publish3)
					#print res1
					#print res2
					#print res3
					
					rawPublish = {}
					rawPublish["r"] = 0
					rawPublish["t"] = post_time
					#print rawPublish
					topic_line = "u/" + unitId + "/"
					#print topic_line+turbine["outputs"]["turbineHeatRate"]
					client.publish(topic_line+turbine["outputs"]["turbineHeatRate"], json.dumps([rawPublish]))
					
				
				#sys.exit()
	WGHTHR = 0.0

	try:
		for i in range(len(mapping["plantHeatRate"]["realtime"]["turbineHeatRate"])):
			WGHTHR = WGHTHR + (mapping["plantHeatRate"]["realtime"]["turbineHeatRate"][i] * mapping["plantHeatRate"]["realtime"]["turbineSteamFlow"][i])
		WGHTHR /= sum(mapping["plantHeatRate"]["realtime"]["turbineSteamFlow"])
	except:
		pass
	#print  WGHTHR   



	for boiler in mapping["boilerEfficiency"]:
		skip_flag = 0
		if len(boiler["fuelProximate"]) > 0 :
			fuelProximateData = getProximateData(boiler["fuelProximate"], boiler["loi"], boiler)
			if fuelProximateData.shape[1]==0:
				#print("Proximate data not found in db, , skipping boiler",boiler["systemInstance"])
				skip_flag = 1
			
			fuelProximateDesignData = boiler["fuelProximateDesign"]
			fuelProximateData = fuelProximateData.to_dict(orient="records")[0]
			if "proximateType" in mapping:
				fuelProximateData["type"] = mapping["proximateType"]
				fuelProximateDesignData["type"] = mapping["proximateType"]
			else:
				fuelProximateData["type"] = mapping["type"]
				fuelProximateDesignData["type"] = mapping["type"]
			
			fuelUltimateData = requests.post(effURL+"proximatetoultimate",json=fuelProximateData)
			if fuelUltimateData.status_code ==200:
				fuelUltimateData = json.loads(fuelUltimateData.content)
			fuelUltimateDesignData = requests.post(effURL+"proximatetoultimate",json=fuelProximateDesignData)
			if fuelUltimateDesignData.status_code ==200:
				fuelUltimateDesignData = json.loads(fuelUltimateDesignData.content)
				
		elif len(boiler["fuelUltimate"]) > 0:
			#print(boiler["fuelUltimate"])
			fuelProximateData , fuelProximateDesignData = {}, {}	
			fuelUltimateData = getUltimateData(boiler["fuelUltimate"], boiler["loi"], boiler)	
			if fuelUltimateData.shape[1]==0:	
				#print("Proximate data not found in db, , skipping boiler",boiler["systemInstance"])	
				skip_flag = 1	
			fuelUltimateData = fuelUltimateData.to_dict(orient="records")[0]	
			fuelUltimateData["type"] = mapping["type"]	
			fuelUltimateDesignData = fuelUltimateData	
			
		else:
			#print("Incorrect mapping, missing fuel properties, skipping boiler",boiler["systemInstance"])
			skip_flag = 1

		fuelData = dict(list(fuelProximateData.items()) + list(fuelUltimateData.items()))
		fuelDesignData = dict(list(fuelProximateDesignData.items()) + list(fuelUltimateDesignData.items()))
		#print fuelDesignData
		del fuelData["time"]

		if len(boiler["realtime"]) > 0 :
			realtimeData = getBoilerRealtimeData(boiler["realtime"])
			#print "******Boiler********* ", boiler["systemInstance"], boiler["realtime"]
			if realtimeData.shape[1]==0:
				#print("realtime data not found in db, , skipping boiler",boiler["systemInstance"])
				skip_flag = 1  
			
			realtimeData = realtimeData.to_dict(orient="records")[0] 
			# print("realtime data to calc boiler efficiency") 
			# print (realtimeData)
			try :
				print("in try of checking threshold")
				
				threshold=getThreshold(str(boiler["realtime"]["boilerSteamFlow"][0]))
				# print("threshold",threshold,"boilersteamflow",realtimeData["boilerSteamFlow"])
				if threshold == None:
					print ("threshold value is NONE considering 10 as threshold")
					threshold = 10
				if realtimeData["boilerSteamFlow"] < threshold:
					skip_flag  = 1
			except Exception as e :
				print("exception",e)
				if realtimeData["boilerSteamFlow"] < 10:
					skip_flag  = 1


			if skip_flag==0:

				realtimeDesignData = requests.post(effURL+"design",json={"realtime":boiler["realtime"],"loi":boiler["loi"],"load":realtimeData["boilerSteamFlow"],"loadTag":boiler["realtime"]["boilerSteamFlow"][0],"realtimeData":realtimeData,"unitId":unitId})
				if realtimeDesignData.status_code ==200:
					realtimeDesignData = json.loads(realtimeDesignData.content)
				#print(realtimeData)
				#print "$" *10
				#print(realtimeDesignData)
				realtimeBPData = requests.post(effURL+"bestachieved",json={"realtime":boiler["realtime"],"load":realtimeData["boilerSteamFlow"],"loadTag":boiler["realtime"]["boilerSteamFlow"][0],"realtimeData":realtimeData,"unitId":unitId})
				if realtimeBPData.status_code ==200:
					realtimeBPData = json.loads(realtimeBPData.content)
					for i,j in realtimeBPData.items():
						# print (i,j)
						if j!=j :
							if (i in realtimeData.keys()):
								realtimeBPData[i] = realtimeData[i]
							
				boilerInputData =  dict(list(fuelData.items()) + list(realtimeData.items()) + list(boiler["assumptions"].items()) + [("type", mapping["type"])] ) 
				boilerInputBPData =  dict(list(fuelData.items()) + list(realtimeBPData.items()) + list(boiler["assumptions"].items()) + [("type", mapping["type"])] ) 
				boilerInputDesignData =  dict(list(fuelDesignData.items()) + list(realtimeDesignData.items()) + list(boiler["assumptions"].items()) + list(boiler["loiDesign"].items()) + [("type", mapping["type"])] ) 
			
				#print("boilerInputDataJson") 
				# print(json.dumps(fuelDesignData, indent=4))
				# print(json.dumps(realtimeDesignData, indent=4))
				# print(json.dumps(fuelDesignData, indent=4))
				# print("boilerInputDesignDataJson")
				# print(json.dumps(boilerInputDesignData, indent=4))
				# print("boilerInputBPData")
				# print(json.dumps(boilerInputBPData, indent=4))
				# print("boilerInputData")
				# print(json.dumps(boilerInputData, indent=4))
				
				
				
				tmp = [boilerInputData, boilerInputBPData, boilerInputDesignData]
				
				inputDf = pd.DataFrame()
				inputDf = pd.read_json(json.dumps(tmp))
				inputDf['inputType'] = ['realTime', 'bestAchieved', 'design']
				inputDf.to_csv(str(unitId + "_input.csv"))
				#print inputDf
				
				boilerEfficiency = requests.post(effURL+"boiler",json=boilerInputData)
				if boilerEfficiency.status_code ==200:
					boilerEfficiency = json.loads(boilerEfficiency.content)

				boilerBPefficiency = requests.post(effURL+"boiler",json=boilerInputBPData)
				if boilerBPefficiency.status_code ==200:
					boilerBPefficiency = json.loads(boilerBPefficiency.content)
				
				boilerDesignEfficiency = requests.post(effURL+"boiler",json=boilerInputDesignData)
				if boilerDesignEfficiency.status_code ==200:
					boilerDesignEfficiency = json.loads(boilerDesignEfficiency.content)
				else:
					print(boilerDesignEfficiency.text)

				print ("STopping here")
				#print json.dumps(boilerInputData)
				print ("boilerEfficiency")
				# print (json.dumps(boilerEfficiency,indent=4))
				if boilerEfficiency["boilerEfficiency"] <50 or boilerEfficiency["boilerEfficiency"] > 90:
					print("rechanging values when B.E is out of limit(50-90) and when its greater than 90 , lossUnaccounted is added")
					old_boiler_efficiency = boilerEfficiency["boilerEfficiency"]
					if old_boiler_efficiency < 50:
						boilerEfficiency["boilerEfficiency"] = 0
					elif old_boiler_efficiency > 90:
						boilerEfficiency["boilerEfficiency"] = 90
						if "LossUnaccounted" in boilerEfficiency:
							loss_unaccounted_value = boilerEfficiency["LossUnaccounted"]
							boilerEfficiency["LossUnaccounted"] = old_boiler_efficiency - 90 + loss_unaccounted_value
						else:
							boilerEfficiency["LossUnaccounted"] = old_boiler_efficiency - 90

				else:
					print("boiler efficiency is within the limit")
					pass
			
				#sys.exit("***********THE END****************")
				
				#print("boilerEfficiency")
				#print(json.dumps(boilerEfficiency, indent=4))
				#print("boilerBPEfficiency")
				#print(json.dumps(boilerBPefficiency, indent=4))
				#print("boilerDesignEfficiency")
				#print(json.dumps(boilerDesignEfficiency, indent=4))
				
				#sys.exit("***********THE END****************")
				if mapping.get("plantHeatRate"):
					mapping["plantHeatRate"]["realtime"]["boilerEfficiency"].append(boilerEfficiency["boilerEfficiency"])
					mapping["plantHeatRate"]["realtime"]["boilerSteamFlow"].append(boilerInputData["boilerSteamFlow"])
					mapping["plantHeatRate"]["design"]["boilerEfficiency"].append(boilerDesignEfficiency["boilerEfficiency"])
					mapping["plantHeatRate"]["design"]["boilerSteamFlow"].append(boilerInputDesignData["boilerSteamFlow"])
					mapping["plantHeatRate"]["bestAchieved"]["boilerEfficiency"].append(boilerBPefficiency["boilerEfficiency"])
					mapping["plantHeatRate"]["bestAchieved"]["boilerSteamFlow"].append(boilerInputBPData["boilerSteamFlow"])
				
				#print boilerEfficiency
				
				
				# coal Calculations 	
				try:	
					if boiler.get("fuelUltimateConfig"):	
						costOfFuel = 0	
						fuelInfo = getLastValues(boiler["fuelUltimateConfig"]["fuelFlow"] + boiler["fuelUltimateConfig"]["landingCost"])	
						for idx, fl in enumerate(boiler["fuelUltimateConfig"]["fuelFlow"]):	
							costOfFuel += (fuelInfo[boiler["fuelUltimateConfig"]["fuelFlow"][idx]] * fuelInfo[boiler["fuelUltimateConfig"]["landingCost"][idx]]).values[0]	
						costPerUnitSteam = costOfFuel / (realtimeData["boilerSteamFlow"])	
						#print "Fuel Flow: ", fuelInfo[boiler["fuelUltimateConfig"]["fuelFlow"]].sum(axis=1).values[0]	
						#print "Cost Of Fuel: ", costOfFuel	
						#print "costPerUnitSteam: ", costPerUnitSteam, realtimeData["boilerSteamFlow"]	
						coalCalResult = {"coalFlow" : fuelInfo[boiler["fuelUltimateConfig"]["fuelFlow"]].sum(axis=1).values[0], "costOfFuel" : costOfFuel, "costPerUnitSteam" : costPerUnitSteam}	
						coalCalDesignResult = coalCalResult.copy()	
						coalCalBPResult = coalCalResult.copy()	
					else:	
						coalCalInputData = boilerInputData.copy()	
						coalCalInputDesignData = boilerInputData.copy()	
						coalCalInputBPData = boilerInputData.copy()	
						coalCalInputData["boilerEfficiency"] = boilerEfficiency["boilerEfficiency"] * 0.01 	
						coalCalInputDesignData["boilerEfficiency"] = boilerDesignEfficiency["boilerEfficiency"] * 0.01	
						coalCalInputBPData["boilerEfficiency"] = boilerBPefficiency["boilerEfficiency"] * 0.01
						#print "####################"	
						coalCalResult = requests.post(effURL+"coalCal",json=coalCalInputData)	
						coalCalDesignResult = requests.post(effURL+"coalCal",json=coalCalInputDesignData)	
						coalCalBPResult = requests.post(effURL+"coalCal",json=coalCalInputBPData)	
						coalCalResult = coalCalResult.json() if (coalCalResult.status_code==200) else coalCalResult.text	
						coalCalDesignResult = coalCalDesignResult.json() if (coalCalDesignResult.status_code==200) else coalCalDesignResult.text	
						coalCalBPResult = coalCalBPResult.json() if (coalCalBPResult.status_code==200) else coalCalBPResult.text	
							
						#print "coalCalInputData: ", json.dumps(coalCalInputData, indent=4)	
						#print "coalCalInputDesignData: ", json.dumps(coalCalInputDesignData, indent=4)	
						#print "coalCalInputBPData: ", json.dumps(coalCalInputBPData, indent=4)	
						#print "coalCalResult: ", json.dumps(coalCalResult, indent=4)	
						#print "coalCalDesignResult: ", json.dumps(coalCalDesignResult, indent=4)	
						#print "coalCalBPResult: ", json.dumps(coalCalBPResult, indent=4)	
						#print "coalCalResult", coalCalResult	
						#print "coalCalDesignResult: ", coalCalDesignResult	
						#print "coalCalBPResult: ", coalCalBPResult
				
				except Exception as e:
					print("EXCEPTION OCCURED, since static way is implemented for mixture calcs")
					coalCalInputData = boilerInputData.copy()	
					coalCalInputDesignData = boilerInputData.copy()	
					coalCalInputBPData = boilerInputData.copy()	
					coalCalInputData["boilerEfficiency"] = boilerEfficiency["boilerEfficiency"] * 0.01 	
					coalCalInputDesignData["boilerEfficiency"] = boilerDesignEfficiency["boilerEfficiency"] * 0.01	
					coalCalInputBPData["boilerEfficiency"] = boilerBPefficiency["boilerEfficiency"] * 0.01
					coalCalResult = requests.post(effURL+"coalCal",json=coalCalInputData)	
					coalCalDesignResult = requests.post(effURL+"coalCal",json=coalCalInputDesignData)	
					coalCalBPResult = requests.post(effURL+"coalCal",json=coalCalInputBPData)	
					coalCalResult = coalCalResult.json() if (coalCalResult.status_code==200) else coalCalResult.text	
					coalCalDesignResult = coalCalDesignResult.json() if (coalCalDesignResult.status_code==200) else coalCalDesignResult.text	
					coalCalBPResult = coalCalBPResult.json() if (coalCalBPResult.status_code==200) else coalCalBPResult.text
				
				
				try:
					entire_input_output_combo_actual = {**boilerEfficiency, **boilerInputData} # (py3.9 and above) boilerEfficiency | boilerInputData # this method is used to merge / combine two dicts to form another dict
					entire_input_output_combo_design = {**boilerDesignEfficiency, **boilerInputDesignData}
					entire_input_output_combo_bperf = {**boilerBPefficiency, **boilerInputBPData}
			
					# print ("\n\n\n")
					# print (entire_input_output_combo_actual, entire_input_output_combo_design, entire_input_output_combo_bperf)
					# print ("\n\n\n")
					post_query_method(entire_input_output_combo_actual, entire_input_output_combo_design, entire_input_output_combo_bperf, assetManagerConfig, boiler, post_time)
				except Exception as e:
					print ("failing relationship new asset managaer method")
					print (e)
					pass

				for loss in boiler["outputs"].keys():
					# print (loss)
					# print (boiler["outputs"][loss])
					# print (round(boilerEfficiency.get(loss)))
					# Post value here
					# print (json.dumps(assetManagerConfig, indent=4))  
					# def generate_query_based_body(original_body, assetManagerConfig, boiler_config, calc_type, loss, measureUnit):
					#     metricName = str(unitId) + "_" + boiler_config["systemName"] + "_asset_manager"
					#     tagsDict = {}
					#     tagsDict["dataTagId"] = ""
					#     tagsDict["parameter"] = assetManagerConfig[boiler_config["systemName"]][boiler_config["outputs"][loss]]
					#     tagsDict["measureUnit"] = str(measureUnit)
					#     tagsDict["calculationType"] = ""
					#     tagsDict["dataTagId"] = boiler_config["outputs"][loss]
					#     tagsDict["calculationType"] = calc_type
					#     query_body_publish1 = [{"name" : metricName, "datapoints" : [[post_time, round(boilerEfficiency.get(loss), 3)]], "tags": tagsDict}]

					#     return query_body_publish1
					try:

						metricName = str(unitId) + "_" + boiler["systemName"] + "_asset_manager"
						tagsDict = {}
						tagsDict["dataTagId"] = ""
						tagsDict["parameter"] = assetManagerConfig[boiler["systemName"]][boiler["outputs"][loss]]
						tagsDict["measureUnit"] = "%"
						tagsDict["calculationType"] = ""
						# query_body_publish_011 = generate_query_based_body(body_publish1, assetManagerConfig, boiler, "actual", loss, "%")
						#print body_publish1

						tagsDict["dataTagId"] = boiler["outputs"][loss]
						tagsDict["calculationType"] = "actual"

						query_body_publish1 = [{"name" : metricName, "datapoints" : [[post_time, round(boilerEfficiency.get(loss), 3)]], "tags": tagsDict}]
						# print (query_body_publish1)
						qr.postDataPacket(query_body_publish1)
						#print body_publish2
						tagsDict["dataTagId"] = boiler["outputs"][loss] + "_des"
						tagsDict["calculationType"] = "design"

						query_body_publish2 = [{"name" : metricName, "datapoints" : [[post_time, round(boilerDesignEfficiency.get(loss), 3)]], "tags": tagsDict}]
						# query_body_publish_011 = generate_query_based_body(body_publish2, assetManagerConfig, boiler, "actual", loss, "%")
						
						# print (query_body_publish2)
						qr.postDataPacket(query_body_publish2)

						#print body_publish3
						tagsDict["dataTagId"] = boiler["outputs"][loss] + "_bperf"
						tagsDict["calculationType"] = "bperf"

						query_body_publish3 = [{"name" : metricName, "datapoints" : [[post_time, round(boilerBPefficiency.get(loss), 3)]], "tags": tagsDict}]
						# print (query_body_publish3)
						qr.postDataPacket(query_body_publish3)

					except Exception as e:
						print (e)
						print ("failing in new method")
						pass

					body_publish1 = [{"name" : boiler["outputs"][loss], "datapoints" : [[post_time, round(boilerEfficiency.get(loss), 3)]], "tags" : {"type": "raw"}}]
					body_publish2 = [{"name" : boiler["outputs"][loss] + "_des", "datapoints" : [[post_time, round(boilerDesignEfficiency.get(loss), 3)]], "tags" : {"type": "raw"}}]
					body_publish3 = [{"name" : boiler["outputs"][loss] + "_bperf", "datapoints" : [[post_time, round(boilerBPefficiency.get(loss), 3)]], "tags" : {"type": "raw"}}]
					
					res1 = qr.postDataPacket(body_publish1)


					#print res1
					res2 = qr.postDataPacket(body_publish2)


					#print res2
					res3 = qr.postDataPacket(body_publish3)

					#print res3
					
					# Publish results to topics
					client.publish(topic_line+boiler["outputs"][loss] + '/r', json.dumps([{"r": body_publish1[0]["datapoints"][0][1], "t": body_publish1[0]["datapoints"][0][0]}]))
					client.publish(topic_line+boiler["outputs"][loss] + "_des" + '/r', json.dumps([{"r": body_publish2[0]["datapoints"][0][1], "t": body_publish2[0]["datapoints"][0][0]}]))
					client.publish(topic_line+boiler["outputs"][loss] + "_bperf" + '/r', json.dumps([{"r": body_publish3[0]["datapoints"][0][1], "t": body_publish3[0]["datapoints"][0][0]}]))
					client.publish("kairoswriteexternal",json.dumps(body_publish1))
					client.publish("kairoswriteexternal",json.dumps(body_publish2))
					client.publish("kairoswriteexternal",json.dumps(body_publish3))
				
				
				for loss in boiler["outputs"].keys():
					#print loss
					deltaLossDesign =  boilerEfficiency[loss] - boilerDesignEfficiency[loss]
					deltaLossBest = boilerEfficiency[loss] - boilerBPefficiency[loss]

					if mapping.get("turbineHeatRate"):
						# print("boiler has turbine")
						if loss != "boilerEfficiency":
							# print("calculating design dev for the loss in kcalkwh ")
							corrDes =  boilerDesignEfficiency["boilerEfficiency"] - deltaLossDesign
							corrBperf =   boilerBPefficiency["boilerEfficiency"] - deltaLossBest
							desDev = ((WGHTHR / corrDes) - (WGHTHR / boilerDesignEfficiency["boilerEfficiency"])) * 100
							bperfDev = ((WGHTHR / corrBperf) - (WGHTHR / boilerBPefficiency["boilerEfficiency"])) * 100
						else:
							# print("calculating design dev for boiler eff loss")
							desDev = ((WGHTHR / boilerDesignEfficiency[loss]) - (WGHTHR / boilerEfficiency["boilerEfficiency"])) * 100
							bperfDev = ((WGHTHR / boilerBPefficiency[loss]) - (WGHTHR / boilerEfficiency["boilerEfficiency"])) * 100
							desDev = -(desDev)
							bperfDev = -(bperfDev)
					else:
						print("boiler doesn't have turbine")
						if loss != "boilerEfficiency":
							desDev, bperfDev = deltaLossDesign, deltaLossBest
						else:
							# desDev, bperfDev = -(desDev), -(bperfDev)
							desDev, bperfDev = deltaLossDesign, deltaLossBest
					
					# Post boiler["outputs"][loss] + "_bperf_dev", boiler["outputs"][loss] +  "_des_dev"
					#print desDev, bperfDev
					try:
						metricName = str(unitId) + "_" + boiler["systemName"] + "_asset_manager"
						tagsDict = {}
						tagsDict["dataTagId"] = ""
						tagsDict["parameter"] = assetManagerConfig[boiler["systemName"]][boiler["outputs"][loss]]
						tagsDict["measureUnit"] = "kCal/kWh"
						tagsDict["calculationType"] = ""
						#print body_publish1

						tagsDict["dataTagId"] = boiler["outputs"][loss] + "_des_dev"
						tagsDict["calculationType"] = "desDev"

						query_body_publish1 = [{"name" : metricName, "datapoints" : [[post_time, round(desDev,3)]], "tags": tagsDict}]
						# print (query_body_publish1)
						qr.postDataPacket(query_body_publish1)


						#print body_publish2
						tagsDict["dataTagId"] = boiler["outputs"][loss] + "_bperf_dev"
						tagsDict["calculationType"] = "bperfDev"

						query_body_publish2 = [{"name" : metricName, "datapoints" : [[post_time, round(bperfDev, 3)]], "tags": tagsDict}]
						# print (query_body_publish2)
						qr.postDataPacket(query_body_publish2)
					except Exception as e:
						print (e)
						print ("failign in new asset manager query method")
						pass

					body_publish1 = [{"name" : boiler["outputs"][loss] + "_des_dev", "datapoints" : [[post_time, round(desDev,3)]], "tags" : {"type": "raw"}}]
					body_publish2 = [{"name" : boiler["outputs"][loss] + "_bperf_dev", "datapoints" : [[post_time, round(bperfDev, 3)]], "tags" : {"type": "raw"}}]

					res1 = qr.postDataPacket(body_publish1)
					#print res1
					res2 = qr.postDataPacket(body_publish2)
					
					# Publish results to topics
					client.publish(topic_line+boiler["outputs"][loss] + "_des_dev" + '/r', json.dumps([{"r": body_publish1[0]["datapoints"][0][1], "t": body_publish1[0]["datapoints"][0][0]}]))
					client.publish(topic_line+boiler["outputs"][loss] + "_bperf_dev" + '/r', json.dumps([{"r": body_publish2[0]["datapoints"][0][1], "t": body_publish2[0]["datapoints"][0][0]}]))
					client.publish("kairoswriteexternal",json.dumps(body_publish1))
					client.publish("kairoswriteexternal",json.dumps(body_publish2))
					  
					
				try:
					#print coalCalResult
					for coalCal in boiler["coalCalOutputs"].keys():
						body_publish1 = [{"name" : boiler["coalCalOutputs"][coalCal], "datapoints" : [[post_time, round(coalCalResult.get(coalCal), 3)]], "tags" : {"type": "coalcal"}}]
						#print body_publish1
						body_publish2 = [{"name" : boiler["coalCalOutputs"][coalCal] + "_des", "datapoints" : [[post_time, round(coalCalDesignResult.get(coalCal), 3)]], "tags" : {"type": "coalcal"}}]
						#print body_publish2
						body_publish3 = [{"name" : boiler["coalCalOutputs"][coalCal] + "_bperf", "datapoints" : [[post_time, round(coalCalBPResult.get(coalCal), 3)]], "tags" : {"type": "coalcal"}}]
						#print body_publish3

						desDev = coalCalResult[coalCal] - coalCalDesignResult[coalCal]
						bperfDev = coalCalResult[coalCal] - coalCalBPResult[coalCal]
						body_publish4 = [{"name" : boiler["coalCalOutputs"][coalCal]  + "_des_dev", "datapoints" : [[post_time, round(desDev, 3)]], "tags" : {"type": "coalcal"}}]
						#print body_publish4
						body_publish5 = [{"name" : boiler["coalCalOutputs"][coalCal] + "_bperf_dev", "datapoints" : [[post_time, round(bperfDev, 3)]], "tags" : {"type": "coalcal"}}]
						#print body_publish5

						res1 = qr.postDataPacket(body_publish1)
						#print res1
						res2 = qr.postDataPacket(body_publish2)
						#print res2
						res3 = qr.postDataPacket(body_publish3)
						#print res3
						res4 = qr.postDataPacket(body_publish4)
						#print res4
						res5 = qr.postDataPacket(body_publish5)
						#print res5
						
						# Publish results to topics
						client.publish(topic_line+boiler["coalCalOutputs"][coalCal] + '/r', json.dumps([{"r": body_publish1[0]["datapoints"][0][1], "t": body_publish1[0]["datapoints"][0][0]}]))
						client.publish(topic_line+boiler["coalCalOutputs"][coalCal] + "_des" + '/r', json.dumps([{"r": body_publish2[0]["datapoints"][0][1], "t": body_publish2[0]["datapoints"][0][0]}]))
						client.publish(topic_line+boiler["coalCalOutputs"][coalCal] + "_bperf" + '/r', json.dumps([{"r": body_publish3[0]["datapoints"][0][1], "t": body_publish3[0]["datapoints"][0][0]}]))
						client.publish(topic_line+boiler["coalCalOutputs"][coalCal] + "_des_dev" + '/r', json.dumps([{"r": body_publish4[0]["datapoints"][0][1], "t": body_publish4[0]["datapoints"][0][0]}]))
						client.publish(topic_line+boiler["coalCalOutputs"][coalCal] + "_bperf_dev" + '/r', json.dumps([{"r": body_publish5[0]["datapoints"][0][1], "t": body_publish5[0]["datapoints"][0][0]}]))
						client.publish("kairoswriteexternal",json.dumps(body_publish1))
						client.publish("kairoswriteexternal",json.dumps(body_publish2))
						client.publish("kairoswriteexternal",json.dumps(body_publish3))
						client.publish("kairoswriteexternal",json.dumps(body_publish4))
						client.publish("kairoswriteexternal",json.dumps(body_publish5))
						 
						
				except Exception as e:
					pass

				for item in boiler["realtime"]:
					#print "*******"
					#print item
					parameterDesignInputData = boilerInputDesignData.copy()
					parameterBperfInputData = boilerInputBPData.copy()
					parameterDesignInputData[item] = realtimeData[item]
					parameterBperfInputData[item] = realtimeData[item]
					#print parameterDesignInputData, parameterBperfInputData
					parameterDesignBoilerEfficiency = requests.post(effURL+"boiler",json=parameterDesignInputData)
					parameterBperfBoilerEfficiency = requests.post(effURL+"boiler",json=parameterBperfInputData)
					if parameterDesignBoilerEfficiency.status_code == 200:
						parameterDesignBoilerEfficiency = json.loads(parameterDesignBoilerEfficiency.content)
						deltaEfficiencyParameterDesign = boilerDesignEfficiency["boilerEfficiency"] - parameterDesignBoilerEfficiency["boilerEfficiency"]
						parameterCorrDes = boilerDesignEfficiency["boilerEfficiency"] - deltaEfficiencyParameterDesign
						parameterDesDev = ((WGHTHR / parameterCorrDes) - (WGHTHR / boilerDesignEfficiency["boilerEfficiency"])) * 100

					if parameterBperfBoilerEfficiency.status_code == 200:
						parameterBperfBoilerEfficiency = json.loads(parameterBperfBoilerEfficiency.content)
						deltaEfficiencyParameterBperf = parameterBperfBoilerEfficiency["boilerEfficiency"] - parameterDesignBoilerEfficiency["boilerEfficiency"]
						parameterCorrBperf = boilerDesignEfficiency["boilerEfficiency"] - deltaEfficiencyParameterBperf
						parameterBperfDev = ((WGHTHR / parameterCorrBperf) - (WGHTHR / boilerBPefficiency["boilerEfficiency"])) * 100

					'''
					# Replace design for realtime item and fetch losses
					parameterDesignInput = boilerInputData.copy()
					parameterDesignInput[item] = realtimeDesignData[item]
					parameterBoilerDesignEfficiency = requests.post(effURL+"boiler",json=parameterDesignInput)
					for loss in boiler["outputs"]:
						parameterDeltaLossDesign = boilerEfficiency[loss] - parameterBoilerDesignEfficiency[loss]
						if parameterDeltaLossDesign != 0:
							paramCorrDes = parameterBoilerDesignEfficiency["boilerEfficiency"] - parameterDeltaLossDesign
							parameterDesDev = ((WGHTHR / paramCorrDes) - (WGHTHR / parameterBoilerDesignEfficiency["boilerEfficiency"])) * 100
					'''
					#print "********************"
					#print deltaEfficiencyParameterDesign, deltaEfficiencyParameterBperf
				
				

			else:
				if mapping.get("plantHeatRate"):
					mapping["plantHeatRate"]["realtime"]["boilerEfficiency"].append(0)
					mapping["plantHeatRate"]["realtime"]["boilerSteamFlow"].append(0)
					mapping["plantHeatRate"]["design"]["boilerEfficiency"].append(0)
					mapping["plantHeatRate"]["design"]["boilerSteamFlow"].append(0)
					mapping["plantHeatRate"]["bestAchieved"]["boilerEfficiency"].append(0)
					mapping["plantHeatRate"]["bestAchieved"]["boilerSteamFlow"].append(0)
					
				
				for loss in boiler["outputs"].keys():
					# Post value here
					body_publish1 = [{"name" : boiler["outputs"][loss], "datapoints" : [[post_time, 0.0]], "tags" : {"type": "raw"}}]
					#print body_publish1
					body_publish2 = [{"name" : boiler["outputs"][loss] + "_des", "datapoints" : [[post_time, 0.0]], "tags" : {"type": "raw"}}]
					#print body_publish2
					body_publish3 = [{"name" : boiler["outputs"][loss] + "_bperf", "datapoints" : [[post_time, 0.0]], "tags" : {"type": "raw"}}]
					#print body_publish3
					body_publish4 = [{"name" : boiler["outputs"][loss] + "_des_dev", "datapoints" : [[post_time, 0.0]], "tags" : {"type": "raw"}}]
					#print body_publish4
					body_publish5 = [{"name" : boiler["outputs"][loss] + "_bperf_dev", "datapoints" : [[post_time, 0.0]], "tags" : {"type": "raw"}}]
					#print body_publish5
					
					
					res1 = qr.postDataPacket(body_publish1)
					#print res1
					res2 = qr.postDataPacket(body_publish2)
					#print res2
					res3 = qr.postDataPacket(body_publish3)
					#print res3
					res4 = qr.postDataPacket(body_publish4)
					#print res4
					res5 = qr.postDataPacket(body_publish5)
					#print res5
					
					# Publish results to topics
					client.publish(topic_line+boiler["outputs"][loss] + '/r', json.dumps([{"r": body_publish1[0]["datapoints"][0][1], "t": body_publish1[0]["datapoints"][0][0]}]))
					client.publish(topic_line+boiler["outputs"][loss] + "_des" + '/r', json.dumps([{"r": body_publish2[0]["datapoints"][0][1], "t": body_publish2[0]["datapoints"][0][0]}]))
					client.publish(topic_line+boiler["outputs"][loss] + "_bperf" + '/r', json.dumps([{"r": body_publish3[0]["datapoints"][0][1], "t": body_publish3[0]["datapoints"][0][0]}]))
					client.publish(topic_line+boiler["outputs"][loss] + "_des_dev" + '/r', json.dumps([{"r": body_publish4[0]["datapoints"][0][1], "t": body_publish4[0]["datapoints"][0][0]}]))
					client.publish(topic_line+boiler["outputs"][loss] + "_bperf_dev" + '/r', json.dumps([{"r": body_publish5[0]["datapoints"][0][1], "t": body_publish5[0]["datapoints"][0][0]}]))
					client.publish("kairoswriteexternal",json.dumps(body_publish1))
					client.publish("kairoswriteexternal",json.dumps(body_publish2))
					client.publish("kairoswriteexternal",json.dumps(body_publish3))
					client.publish("kairoswriteexternal",json.dumps(body_publish4))
					client.publish("kairoswriteexternal",json.dumps(body_publish5))
			
				
	 
				for coalCal in boiler["coalCalOutputs"].keys():
					body_publish1 = [{"name" : boiler["coalCalOutputs"][coalCal], "datapoints" : [[post_time, 0.0]], "tags" : {"type": "coalcal"}}]
					#print body_publish1
					body_publish2 = [{"name" : boiler["coalCalOutputs"][coalCal] + "_des", "datapoints" : [[post_time, 0.0]], "tags" : {"type": "coalcal"}}]
					#print body_publish2
					body_publish3 = [{"name" : boiler["coalCalOutputs"][coalCal] + "_bperf", "datapoints" : [[post_time, 0.0]], "tags" : {"type": "coalcal"}}]
					#print body_publish3

					body_publish4 = [{"name" : boiler["coalCalOutputs"][coalCal]  + "_des_dev", "datapoints" : [[post_time, 0.0]], "tags" : {"type": "coalcal"}}]
					#print body_publish4
					body_publish5 = [{"name" : boiler["coalCalOutputs"][coalCal] + "_bperf_dev", "datapoints" : [[post_time, 0.0]], "tags" : {"type": "coalcal"}}]
					#print body_publish5

					res1 = qr.postDataPacket(body_publish1)
					#print res1
					res2 = qr.postDataPacket(body_publish2)
					#print res2
					res3 = qr.postDataPacket(body_publish3)
					#print res3
					res4 = qr.postDataPacket(body_publish4)
					#print res4
					res5 = qr.postDataPacket(body_publish5)
					#print res5
					
					# Publish results to topics
					client.publish(topic_line+boiler["coalCalOutputs"][coalCal] + '/r', json.dumps([{"r": body_publish1[0]["datapoints"][0][1], "t": body_publish1[0]["datapoints"][0][0]}]))
					client.publish(topic_line+boiler["coalCalOutputs"][coalCal] + "_des" + '/r', json.dumps([{"r": body_publish2[0]["datapoints"][0][1], "t": body_publish2[0]["datapoints"][0][0]}]))
					client.publish(topic_line+boiler["coalCalOutputs"][coalCal] + "_bperf" + '/r', json.dumps([{"r": body_publish3[0]["datapoints"][0][1], "t": body_publish3[0]["datapoints"][0][0]}]))
					client.publish(topic_line+boiler["coalCalOutputs"][coalCal] + "_des_dev" + '/r', json.dumps([{"r": body_publish4[0]["datapoints"][0][1], "t": body_publish4[0]["datapoints"][0][0]}]))
					client.publish(topic_line+boiler["coalCalOutputs"][coalCal] + "_bperf_dev" + '/r', json.dumps([{"r": body_publish5[0]["datapoints"][0][1], "t": body_publish5[0]["datapoints"][0][0]}]))
					client.publish("kairoswriteexternal",json.dumps(body_publish1))
					client.publish("kairoswriteexternal",json.dumps(body_publish2))
					client.publish("kairoswriteexternal",json.dumps(body_publish3))
					client.publish("kairoswriteexternal",json.dumps(body_publish4))
					client.publish("kairoswriteexternal",json.dumps(body_publish5))

			

	if mapping.get("plantHeatRate"):
		print("unit has plant heat rate calc printing plantheatrate realtime values")
		# print(mapping["plantHeatRate"]["realtime"])
		# print(mapping["plantHeatRate"]["design"])
		# print(mapping["plantHeatRate"]["bestAchieved"])
		phr = requests.post(effURL+"phr",json=mapping["plantHeatRate"]["realtime"])
		phrDesign = requests.post(effURL+"phr",json=mapping["plantHeatRate"]["design"])
		phrBp = requests.post(effURL+"phr",json=mapping["plantHeatRate"]["bestAchieved"])
		if phr.status_code ==200:
			phr = json.loads(phr.content)       
			# Post value here
			# if phr["plantHeatRate"] !=0:
			if "averageBoilerEfficiency" in mapping["plantHeatRate"]["outputs"]:
				body_publish1 = [{"name" : mapping["plantHeatRate"]["outputs"]["averageBoilerEfficiency"], "datapoints" : [[post_time, round(phr["averageBoilerEfficiency"], 3)]], "tags" : {"type": "plant_heat_rate"}}]
				print (body_publish1, "%"*30)
				client.publish("kairoswriteexternal",json.dumps(body_publish1))
				client.publish(topic_line + mapping["plantHeatRate"]["outputs"]["averageBoilerEfficiency"] + '/r', json.dumps([{"r": body_publish1[0]["datapoints"][0][1], "t": body_publish1[0]["datapoints"][0][0]}]))	
				res = qr.postDataPacket(body_publish1)
			body_publish1 = [{"name" : mapping["plantHeatRate"]["outputs"]["plantHeatRate"], "datapoints" : [[post_time, round(phr["plantHeatRate"], 3)]], "tags" : {"type": "plant_heat_rate"}}]
			client.publish("kairoswriteexternal",json.dumps(body_publish1))
			client.publish(topic_line + str(mapping["plantHeatRate"]["outputs"]["plantHeatRate"]) + '/r', json.dumps([{"r": round(phr["plantHeatRate"], 3), "t": post_time}]))
			
				#print body_publish
			res = qr.postDataPacket(body_publish1)
			print ("plantHeatRate",phr)
		if phrDesign.status_code ==200:
			if "averageBoilerEfficiency" in mapping["plantHeatRate"]["outputs"]:
				body_publish1 = [{"name" : mapping["plantHeatRate"]["outputs"]["averageBoilerEfficiency"]+"_des", "datapoints" : [[post_time, round(phr["averageBoilerEfficiency"], 3)]], "tags" : {"type": "plant_heat_rate"}}]
				print (body_publish1, "%"*30)
				client.publish("kairoswriteexternal",json.dumps(body_publish1))
				client.publish(topic_line + mapping["plantHeatRate"]["outputs"]["averageBoilerEfficiency"]+"_des" + '/r', json.dumps([{"r": body_publish1[0]["datapoints"][0][1], "t": body_publish1[0]["datapoints"][0][0]}]))
				res = qr.postDataPacket(body_publish1)
			phrDesign = json.loads(phrDesign.content)     
			body_publish2 = [{"name" : mapping["plantHeatRate"]["outputs"]["plantHeatRate"]+"_des", "datapoints" : [[post_time, round(phrDesign["plantHeatRate"], 3)]], "tags" : {"type": "plant_heat_rate"}}]
				#print body_publish
			client.publish("kairoswriteexternal",json.dumps(body_publish2))
			res = qr.postDataPacket(body_publish2)
			client.publish(topic_line + str(mapping["plantHeatRate"]["outputs"]["plantHeatRate"]) + "_des" + '/r', json.dumps([{"r": round(phrDesign["plantHeatRate"], 3), "t": post_time}]))
			print ("plantHeatRatedesign",phrDesign)
		if phrBp.status_code ==200:
			if "averageBoilerEfficiency" in mapping["plantHeatRate"]["outputs"]:
				body_publish1 = [{"name" : mapping["plantHeatRate"]["outputs"]["averageBoilerEfficiency"]+"_bperf", "datapoints" : [[post_time, round(phr["averageBoilerEfficiency"], 3)]], "tags" : {"type": "plant_heat_rate"}}]
				print (body_publish1, "%"*30)
				client.publish("kairoswriteexternal",json.dumps(body_publish1))
				client.publish(topic_line + str(mapping["plantHeatRate"]["outputs"]["averageBoilerEfficiency"])+"_bperf" + '/r', json.dumps([{"r": body_publish1[0]["datapoints"][0][1], "t": body_publish1[0]["datapoints"][0][0]}]))
				res = qr.postDataPacket(body_publish1)
			phrBp = json.loads(phrBp.content) 
			body_publish3 = [{"name" : mapping["plantHeatRate"]["outputs"]["plantHeatRate"]+"_bperf", "datapoints" : [[post_time, round(phrBp["plantHeatRate"], 3)]], "tags" : {"type": "plant_heat_rate"}}]
				#print body_publish
			client.publish("kairoswriteexternal",json.dumps(body_publish3))
			client.publish(topic_line + mapping["plantHeatRate"]["outputs"]["plantHeatRate"]+"_bperf" + '/r', json.dumps([{"r": round(phrBp["plantHeatRate"], 3), "t": post_time}]))
			res = qr.postDataPacket(body_publish3)
				#print res
			print ("plantHeatRatebperf",phrBp)
	# """


	# entire_input_output_combo_actual, entire_input_output_combo_design, entire_input_output_combo_bperf
	if unitId == "6375e28c32ebf700068ac0aa":
		suffixes = ["", "_bperf", "_des"]
		# calc_type = ["actual", "design", "bperf"]
		calc_type = ["actual", "bperf", "design"]

		jsw_thr_dev_result = []
		required_params = [
			[entire_input_output_combo_actual, thr],
			[entire_input_output_combo_bperf, thrBP],
			[entire_input_output_combo_design, thrDesign]
		]
		# required_params = [[{'LossDueToDryFlueGas': 6.931933517713623, 'LossDueToH2InFuel': 3.7447591241797533, 'LossDueToH2OInAir': 0.2090785358909082, 'LossDueToH2OInFuel': 1.2429237099035817, 'LossDueToPartialCombustion': 0.0, 'LossDueToRadiation': 0.5, 'LossDueToUnburntCarbon': 0.4358833042307102, 'LossTotal': 13.554578191918578, 'actualMassOfAirSupplied': 13.74849554267857, 'aphLeakagePassA': 17.406519758832978, 'aphLeakagePassB': 39.94362055056036, 'avgO2AtAphOutlet': 8.338598251342773, 'boilerEfficiency': 86.44542180808142, 'carbonInAsh': 2.457040296, 'carbonInAshPerKgOfFuel': 0.0032739848925457745, 'empiricalCO2': 10.341401748657226, 'excessAirSupplied': 65.85841296937839, 'flueGasTempForNOAphLeakage': 95.6938839910232, 'massOfDryFlueGas': 14.04443784242859, 'moistureContentInAir': 0.017117213001379018, 'relationship': {'actualMassOfAirSupplied': ['LossDueToH2OInAir'], 'ambientAirPressurePascal': ['LossDueToH2OInAir'], 'ambientAirTemp': ['LossDueToH2OInAir', 'LossDueToH2OInFuel', 'LossDueToH2InFuel', 'LossDueToDryFlueGas'], 'ambientRelativeHumidityPRC': ['LossDueToH2OInAir'], 'aphFlueGasOutletO2_A': ['LossDueToH2OInAir', 'LossDueToDryFlueGas'], 'aphFlueGasOutletO2_B': ['LossDueToH2OInAir', 'LossDueToDryFlueGas'], 'aphFlueGasOutletTemp': ['LossDueToH2OInAir', 'LossDueToH2OInFuel', 'LossDueToH2InFuel', 'LossDueToDryFlueGas'], 'avgO2AtAphOutlet': ['LossDueToH2OInAir', 'LossDueToDryFlueGas'], 'bedAshUnburntCarbon': ['LossDueToUnburntCarbon', 'LossDueToDryFlueGas'], 'carbon': ['LossDueToH2OInAir', 'LossDueToDryFlueGas'], 'carbonInAsh': ['LossDueToDryFlueGas'], 'carbonInAshPerKgOfFuel': ['LossDueToDryFlueGas'], 'coalAsh': ['LossDueToUnburntCarbon', 'LossDueToDryFlueGas'], 'coalGCV': ['LossDueToUnburntCarbon', 'LossDueToH2OInAir', 'LossDueToH2OInFuel', 'LossDueToH2InFuel', 'LossDueToDryFlueGas'], 'coalMoist': ['LossDueToH2OInFuel'], 'coalSulphur': ['LossDueToH2OInAir', 'LossDueToDryFlueGas'], 'empiricalCO2': ['LossDueToDryFlueGas'], 'excessAirSupplied': ['LossDueToH2OInAir'], 'flyAshUnburntCarbon': ['LossDueToUnburntCarbon', 'LossDueToDryFlueGas'], 'hydrogen': ['LossDueToH2OInAir', 'LossDueToH2InFuel'], 'moistureContentInAir': ['LossDueToH2OInAir'], 'oxygen': ['LossDueToH2OInAir'], 'saturationVaporPressure': ['LossDueToH2OInAir'], 'sensibleHeatOfDryGas': ['LossDueToDryFlueGas'], 'sensibleHeatOfWater': ['LossDueToH2OInFuel', 'LossDueToH2InFuel'], 'specificHumidity': ['LossDueToH2OInAir'], 'theoriticalAirRequired': ['LossDueToH2OInAir'], 'totalUnburntCarbonInAsh': ['LossDueToUnburntCarbon'], 'vaporPressure': ['LossDueToH2OInAir'], 'weightOfDryFlueGas': ['LossDueToDryFlueGas'], 'weightedAphInletTemp': ['LossDueToH2OInAir', 'LossDueToH2OInFuel', 'LossDueToH2InFuel', 'LossDueToDryFlueGas']}, 'saturationVaporPressure': 3.0234484115947686, 'sensibleHeatOfDryGas': 1718.933403219364, 'sensibleHeatOfWater': 2663.6437832031247, 'specificHumidity': 0.016829144942762667, 'theoriticalAirRequired': 8.28929645264174, 'totalUnburntCarbonInAsh': 0.0031935417644509724, 'vaporPressure': 2.5699311498555533, 'weightOfDryFlueGas': 0.48039695919986575, 'weightedAphInletTemp': 24.22, 'coalGCV': 5922.8218592555, 'hydrogen': 3.87355650441048, 'coalMoist': 11.5710558548511, 'carbon': 59.6727371390005, 'coalSulphur': 0.721959448746531, 'coalAsh': 12.9975148134525, 'nitrogen': 1.4480122094269, 'oxygen': 9.71516403011202, 'bedAshUnburntCarbon': 8.825556, 'flyAshUnburntCarbon': 1.74942744, 'type': 'type14', 'time': 1721460240000, 'paOLTemp': 37.061954498291016, 'aphFlueGasInletTemp': 299.6851806640625, 'ecoOutletCO2': 4.830439567565918, 'aphFlueGasInletO2_A': 6.134688854217529, 'fdOLTemp': 28.153852462768555, 'aphFlueGasInletO2_B': 3.36446476, 'aphFlueGasOutletO2_A': 8.338598251342773, 'aphFlueGasOutletO2_B': 8.398114204406738, 'fdFlow': 494.06329345703125, 'ambientRelativeHumidityPRC': 0.85, 'boilerSteamFlow': 461.79888916015625, 'paFlow': 237.10403442382812, 'ambientAirPressurePascal': 0.9595529564122305, 'ambientAirTemp': 24.22, 'aphFlueGasOutletTemp': 141.153076171875, 'BLR_OFFSET': 0, 'Other_Losses_Plant_Specific_prc': 0, 'partialCombustionLoss': 0.01, 'LossUnaccounted': 0.25, 'airHumidityFactor': 0.016}, {'CondenserVacuum': -90.10539245605469, 'DripHph6Enthalpy': 0.0, 'DripHph6EnthalpyConstant': 0.36, 'DripHph7Enthalpy': 675.6797504821621, 'DripHph7EnthalpyConstant': -0.48, 'DripHph8Enthalpy': 921.8141481885343, 'DripTemperatureHph6': 77.24110412597656, 'DripTemperatureHph7': 160.14572143554688, 'DripTemperatureHph8': 215.34921264648438, 'ExtractionSteamFlowHph6': 0.0, 'ExtractionSteamFlowHph7': 43.49296072664514, 'ExtractionSteamFlowHph8': 29.641305394579863, 'ExtractionSteamHph5Enthalpy': 3183.8891471330353, 'ExtractionSteamHph6Enthalpy': 0.0, 'ExtractionSteamHph6EnthalpyConstant': 0.43, 'ExtractionSteamHph7Enthalpy': 3093.996282126542, 'ExtractionSteamHph7EnthalpyConstant': -0.43, 'ExtractionSteamHph8Enthalpy': 3158.0814040847854, 'ExtractionSteamHph8EnthalpyConstant': -0.5, 'ExtractionSteamPressureHph6': -0.0060431258752942085, 'ExtractionSteamPressureHph7': 1.6521540880203247, 'ExtractionSteamPressureHph8': 3.0611867904663086, 'ExtractionSteamTempHph6': 451.267578125, 'ExtractionSteamTempHph7': 327.21380615234375, 'ExtractionSteamTempHph8': 368.8856201171875, 'FWFinalPress': 12.636999130249023, 'FWFinalTemp': 242.75531005859375, 'FeedWaterFlow': 466.5550231933594, 'FeedWaterInletBeforeEcoEnthalpy': 1050.9156149677333, 'FeedWaterInletTempToHph6': 119.19986724853516, 'FeedWaterInletTempToHph7': 155.28941345214844, 'FeedWaterInletTempToHph8': 210.5673828125, 'FeedWaterInletToHph6Enthalpy': 0.0, 'FeedWaterInletToHph6EnthalpyConstant': 0.19, 'FeedWaterInletToHph7Enthalpy': 661.8752855215142, 'FeedWaterInletToHph7EnthalpyConstant': 0.04, 'FeedWaterInletToHph8Enthalpy': 903.3665363010996, 'FeedWaterInletToHph8EnthalpyConstant': -0.14, 'FeedWaterOutletTempToHph8': 241.58985900878906, 'FeedWaterOutletToHph6Enthalpy': 0.0, 'FeedWaterOutletToHph6EnthalpyConstant': 0.2, 'FeedWaterOutletToHph7Enthalpy': 903.3665363010996, 'FeedWaterOutletToHph7EnthalpyConstant': -0.14, 'FeedWaterOutletToHph8Enthalpy': 1045.4416986736378, 'FeedWaterOutletToHph8EnthalpyConstant': -0.01, 'GlandSteamFlow_LeakOff_InterStageLeakage': 18.181, 'HptExhaustPressure': 1.7406033277511597, 'HptExhaustTemp': 327.6407775878906, 'HptSteamExhaustEnthalpy': 3093.293028393175, 'HrhSteamFlow': 369.9621996990875, 'IptExhaustPressure': 410.3145446777344, 'IptExhaustTemp': 358.010986328125, 'IptInletSteamEnthalpy': 3560.063440577578, 'IptInletSteamPress': 1.5739597082138062, 'IptInletSteamTemp': 539.859375, 'LptExhaustSteamTemp': 45.805938720703125, 'RhSprayWater': 12.945927619934082, 'RhSprayWaterEnthalpy': 650.8081955267928, 'ShRhSprayWaterTemp': 152.70237731933594, 'ShSprayWater01': 32.98841094970703, 'ShSprayWater02': 0.0, 'ShSprayWaterEnthalpy': 650.8081955267928, 'SprayWaterEnthalpyConstant': 0.05, 'category': 'pressureInMpa', 'computedMainSteamFlow_computedFWFlow': 514.3302317802559, 'condensateFlow': 439.8717, 'condensateInletHph5Enthalpy': 511.73244868059976, 'condensateInletTempHph5': 121.9765853881836, 'condensateInletWaterPress': 0.46884581446647644, 'condensateOutletHph5Enthalpy': 508.63914090007125, 'condensateTemp': 46.63983154296875, 'condenserCondensateInletTemp': 41.461265563964844, 'condenserCondensateOutletTemp': 32.202152252197266, 'condenserTTD': 2.9760023929949284, 'enthalpyFW': 1050.9156149677333, 'enthalpyMS': 3437.3409941982486, 'extractionSteamFlowHph5': 14.25919327896496, 'extractionSteamPressureHph5': 0.4247584939002991, 'extractionSteamTempHph5': 357.0873718261719, 'finalFeedWaterFlow_CalculatedFromCondensateFlow': 481.3418208305489, 'hotwellMakeUpFlow': 0.31589069962501526, 'load': 149.37266540527344, 'steamFlowMS': 461.2774658203125, 'steamPressureMS': 11.963787078857422, 'steamTempMS': 532.9227294921875, 'time': 1721460120000, 'totalShSprayWater': 32.98841094970703, 'turbineHeatRate': 2118.037249989759}], [{'LossDueToDryFlueGas': 6.970002402451766, 'LossDueToH2InFuel': 3.7447591241797533, 'LossDueToH2OInAir': 0.2090785358909082, 'LossDueToH2OInFuel': 1.2429237099035817, 'LossDueToPartialCombustion': 0.0, 'LossDueToRadiation': 0.5, 'LossDueToUnburntCarbon': 0.0, 'LossTotal': 13.156763772426011, 'actualMassOfAirSupplied': 13.74849554267857, 'aphLeakagePassA': 17.406519758832978, 'aphLeakagePassB': 39.94362055056036, 'avgO2AtAphOutlet': 8.338598251342773, 'boilerEfficiency': 86.84323622757398, 'carbonInAsh': 0.0, 'carbonInAshPerKgOfFuel': 0.0, 'empiricalCO2': 10.341401748657226, 'excessAirSupplied': 65.85841296937839, 'flueGasTempForNOAphLeakage': 95.6938839910232, 'massOfDryFlueGas': 14.04443784242859, 'moistureContentInAir': 0.017117213001379018, 'relationship': {'actualMassOfAirSupplied': ['LossDueToH2OInAir'], 'ambientAirPressurePascal': ['LossDueToH2OInAir'], 'ambientAirTemp': ['LossDueToH2OInAir', 'LossDueToH2OInFuel', 'LossDueToH2InFuel', 'LossDueToDryFlueGas'], 'ambientRelativeHumidityPRC': ['LossDueToH2OInAir'], 'aphFlueGasOutletO2_A': ['LossDueToH2OInAir', 'LossDueToDryFlueGas'], 'aphFlueGasOutletO2_B': ['LossDueToH2OInAir', 'LossDueToDryFlueGas'], 'aphFlueGasOutletTemp': ['LossDueToH2OInAir', 'LossDueToH2OInFuel', 'LossDueToH2InFuel', 'LossDueToDryFlueGas'], 'avgO2AtAphOutlet': ['LossDueToH2OInAir', 'LossDueToDryFlueGas'], 'bedAshUnburntCarbon': ['LossDueToUnburntCarbon', 'LossDueToDryFlueGas'], 'carbon': ['LossDueToH2OInAir', 'LossDueToDryFlueGas'], 'carbonInAsh': ['LossDueToDryFlueGas'], 'carbonInAshPerKgOfFuel': ['LossDueToDryFlueGas'], 'coalAsh': ['LossDueToUnburntCarbon', 'LossDueToDryFlueGas'], 'coalGCV': ['LossDueToUnburntCarbon', 'LossDueToH2OInAir', 'LossDueToH2OInFuel', 'LossDueToH2InFuel', 'LossDueToDryFlueGas'], 'coalMoist': ['LossDueToH2OInFuel'], 'coalSulphur': ['LossDueToH2OInAir', 'LossDueToDryFlueGas'], 'empiricalCO2': ['LossDueToDryFlueGas'], 'excessAirSupplied': ['LossDueToH2OInAir'], 'flyAshUnburntCarbon': ['LossDueToUnburntCarbon', 'LossDueToDryFlueGas'], 'hydrogen': ['LossDueToH2OInAir', 'LossDueToH2InFuel'], 'moistureContentInAir': ['LossDueToH2OInAir'], 'oxygen': ['LossDueToH2OInAir'], 'saturationVaporPressure': ['LossDueToH2OInAir'], 'sensibleHeatOfDryGas': ['LossDueToDryFlueGas'], 'sensibleHeatOfWater': ['LossDueToH2OInFuel', 'LossDueToH2InFuel'], 'specificHumidity': ['LossDueToH2OInAir'], 'theoriticalAirRequired': ['LossDueToH2OInAir'], 'totalUnburntCarbonInAsh': ['LossDueToUnburntCarbon'], 'vaporPressure': ['LossDueToH2OInAir'], 'weightOfDryFlueGas': ['LossDueToDryFlueGas'], 'weightedAphInletTemp': ['LossDueToH2OInAir', 'LossDueToH2OInFuel', 'LossDueToH2InFuel', 'LossDueToDryFlueGas']}, 'saturationVaporPressure': 3.0234484115947686, 'sensibleHeatOfDryGas': 1728.3734645575873, 'sensibleHeatOfWater': 2663.6437832031247, 'specificHumidity': 0.016829144942762667, 'theoriticalAirRequired': 8.28929645264174, 'totalUnburntCarbonInAsh': 0.0, 'vaporPressure': 2.5699311498555533, 'weightOfDryFlueGas': 0.483035209613203, 'weightedAphInletTemp': 24.22, 'time': 1721349840000, 'coalGCV': 5922.8218592555, 'hydrogen': 3.87355650441048, 'coalMoist': 11.5710558548511, 'carbon': 59.6727371390005, 'coalSulphur': 0.721959448746531, 'coalAsh': 12.9975148134525, 'nitrogen': 1.4480122094269, 'oxygen': 9.71516403011202, 'bedAshUnburntCarbon': 0, 'flyAshUnburntCarbon': 0, 'type': 'type14', 'ambientAirPressurePascal': 0.9595529564122305, 'ambientAirTemp': 24.22, 'ambientRelativeHumidityPRC': 0.85, 'aphFlueGasInletO2_A': 6.134688854217529, 'aphFlueGasInletO2_B': 3.36446476, 'aphFlueGasInletTemp': 299.6851806640625, 'aphFlueGasOutletO2_A': 8.338598251342773, 'aphFlueGasOutletO2_B': 8.398114204406738, 'aphFlueGasOutletTemp': 141.153076171875, 'boilerSteamFlow': 461.79888916015625, 'ecoOutletCO2': 4.830439567565918, 'fdFlow': 494.06329345703125, 'fdOLTemp': 28.153852462768555, 'paFlow': 237.10403442382812, 'paOLTemp': 37.061954498291016, 'BLR_OFFSET': 0, 'Other_Losses_Plant_Specific_prc': 0, 'partialCombustionLoss': 0.01, 'LossUnaccounted': 0.25, 'airHumidityFactor': 0.016}, {'CondenserVacuum': -91.003, 'DripHph6Enthalpy': 2714.768091636763, 'DripHph6EnthalpyConstant': 0.36, 'DripHph7Enthalpy': 676.1885204271687, 'DripHph7EnthalpyConstant': -0.48, 'DripHph8Enthalpy': 900.8190691859434, 'DripTemperatureHph6': 121.825, 'DripTemperatureHph7': 160.258, 'DripTemperatureHph8': 210.745, 'ExtractionSteamFlowHph6': 0.0, 'ExtractionSteamFlowHph7': 43.12025111509269, 'ExtractionSteamFlowHph8': 30.026403863630676, 'ExtractionSteamHph5Enthalpy': 3154.4001623660647, 'ExtractionSteamHph6Enthalpy': 3359.4775393286614, 'ExtractionSteamHph6EnthalpyConstant': 0.43, 'ExtractionSteamHph7Enthalpy': 3051.886560354427, 'ExtractionSteamHph7EnthalpyConstant': -0.43, 'ExtractionSteamHph8Enthalpy': 3101.237692794477, 'ExtractionSteamHph8EnthalpyConstant': -0.5, 'ExtractionSteamPressureHph6': 0.154, 'ExtractionSteamPressureHph7': 1.69, 'ExtractionSteamPressureHph8': 3.037, 'ExtractionSteamTempHph6': 439.166, 'ExtractionSteamTempHph7': 308.724, 'ExtractionSteamTempHph8': 344.442, 'FWFinalPress': 13.498, 'FWFinalTemp': 240.121, 'FeedWaterFlow': 459.736, 'FeedWaterInletBeforeEcoEnthalpy': 1038.7276127128603, 'FeedWaterInletTempToHph6': 128.724, 'FeedWaterInletTempToHph7': 153.484, 'FeedWaterInletTempToHph8': 208.083, 'FeedWaterInletToHph6Enthalpy': 549.1803128796141, 'FeedWaterInletToHph6EnthalpyConstant': 0.19, 'FeedWaterInletToHph7Enthalpy': 654.678877343891, 'FeedWaterInletToHph7EnthalpyConstant': 0.04, 'FeedWaterInletToHph8Enthalpy': 892.5884590943543, 'FeedWaterInletToHph8EnthalpyConstant': -0.14, 'FeedWaterOutletTempToHph8': 239.603, 'FeedWaterOutletToHph6Enthalpy': 654.438877343891, 'FeedWaterOutletToHph6EnthalpyConstant': 0.2, 'FeedWaterOutletToHph7Enthalpy': 892.5884590943543, 'FeedWaterOutletToHph7EnthalpyConstant': -0.14, 'FeedWaterOutletToHph8Enthalpy': 1036.3028044175924, 'FeedWaterOutletToHph8EnthalpyConstant': -0.01, 'GlandSteamFlow_LeakOff_InterStageLeakage': 18.181, 'HptExhaustPressure': 1.741, 'HptExhaustTemp': 309.263, 'HptSteamExhaustEnthalpy': 3052.183318467419, 'HrhSteamFlow': 367.26234502127664, 'IptExhaustPressure': 410.3145446777344, 'IptExhaustTemp': 358.010986328125, 'IptInletSteamEnthalpy': 3534.3745444897645, 'IptInletSteamPress': 1.566, 'IptInletSteamTemp': 528.172, 'LptExhaustSteamTemp': 45.805938720703125, 'MakeUpWaterFlow': 0.895, 'RhSprayWater': 0.77, 'RhSprayWaterEnthalpy': 633.9253747433712, 'ShRhSprayWaterTemp': 148.624, 'ShSprayWater01': 11.384, 'ShSprayWater02': 0.0, 'ShSprayWaterEnthalpy': 633.9253747433712, 'SprayWaterEnthalpyConstant': 0.05, 'category': 'pressureInMpa', 'computedMainSteamFlow_computedFWFlow': 406.9694856649383, 'condensateFlow': 391.921, 'condensateInletHph5Enthalpy': 500.01064117556007, 'condensateInletTempHph5': 119.224, 'condensateInletWaterPress': 0.422, 'condensateOutletHph5Enthalpy': 548.8476859826579, 'condensateTemp': 45.276, 'condenserCondensateInletTemp': 40.589, 'condenserCondensateOutletTemp': 31.429, 'condenserTTD': 0.0, 'enthalpyFW': 1038.7276127128603, 'enthalpyMS': 3412.1209698288544, 'extractionSteamFlowHph5': -57.33916931378508, 'extractionSteamPressureHph5': 0.4, 'extractionSteamTempHph5': 342.588, 'finalFeedWaterFlow_CalculatedFromCondensateFlow': 395.5854856649383, 'hotwellMakeUpFlow': 0.895, 'load': 147.047, 'steamFlowMS': 458.59, 'steamPressureMS': 12.783, 'steamTempMS': 526.84, 'totalShSprayWater': 11.384, 'turbineHeatRate': 2067.045772717949}], [{'LossDueToDryFlueGas': 5.631406652837735, 'LossDueToH2InFuel': 3.696938195753826, 'LossDueToH2OInAir': 0.0, 'LossDueToH2OInFuel': 1.2270514564957724, 'LossDueToPartialCombustion': 0.0, 'LossDueToRadiation': 0.5, 'LossDueToUnburntCarbon': 0.4358833042307102, 'LossTotal': 11.981279609318044, 'actualMassOfAirSupplied': 13.308503479011966, 'aphLeakagePassA': 25.24464831804281, 'aphLeakagePassB': -0.3548845012259685, 'avgO2AtAphOutlet': 7.92, 'boilerEfficiency': 88.01872039068195, 'carbonInAsh': 2.457040296, 'carbonInAshPerKgOfFuel': 0.0032739848925457745, 'empiricalCO2': 10.76, 'excessAirSupplied': 60.550458715596335, 'flueGasTempForNOAphLeakage': 102.54647890627498, 'massOfDryFlueGas': 13.604445778761988, 'moistureContentInAir': 0.0, 'relationship': {'actualMassOfAirSupplied': ['LossDueToH2OInAir'], 'ambientAirPressurePascal': ['LossDueToH2OInAir'], 'ambientAirTemp': ['LossDueToH2OInAir', 'LossDueToH2OInFuel', 'LossDueToH2InFuel', 'LossDueToDryFlueGas'], 'ambientRelativeHumidityPRC': ['LossDueToH2OInAir'], 'aphFlueGasOutletO2_A': ['LossDueToH2OInAir', 'LossDueToDryFlueGas'], 'aphFlueGasOutletO2_B': ['LossDueToH2OInAir', 'LossDueToDryFlueGas'], 'aphFlueGasOutletTemp': ['LossDueToH2OInAir', 'LossDueToH2OInFuel', 'LossDueToH2InFuel', 'LossDueToDryFlueGas'], 'avgO2AtAphOutlet': ['LossDueToH2OInAir', 'LossDueToDryFlueGas'], 'bedAshUnburntCarbon': ['LossDueToUnburntCarbon', 'LossDueToDryFlueGas'], 'carbon': ['LossDueToH2OInAir', 'LossDueToDryFlueGas'], 'carbonInAsh': ['LossDueToDryFlueGas'], 'carbonInAshPerKgOfFuel': ['LossDueToDryFlueGas'], 'coalAsh': ['LossDueToUnburntCarbon', 'LossDueToDryFlueGas'], 'coalGCV': ['LossDueToUnburntCarbon', 'LossDueToH2OInAir', 'LossDueToH2OInFuel', 'LossDueToH2InFuel', 'LossDueToDryFlueGas'], 'coalMoist': ['LossDueToH2OInFuel'], 'coalSulphur': ['LossDueToH2OInAir', 'LossDueToDryFlueGas'], 'empiricalCO2': ['LossDueToDryFlueGas'], 'excessAirSupplied': ['LossDueToH2OInAir'], 'flyAshUnburntCarbon': ['LossDueToUnburntCarbon', 'LossDueToDryFlueGas'], 'hydrogen': ['LossDueToH2OInAir', 'LossDueToH2InFuel'], 'moistureContentInAir': ['LossDueToH2OInAir'], 'oxygen': ['LossDueToH2OInAir'], 'saturationVaporPressure': ['LossDueToH2OInAir'], 'sensibleHeatOfDryGas': ['LossDueToDryFlueGas'], 'sensibleHeatOfWater': ['LossDueToH2OInFuel', 'LossDueToH2InFuel'], 'specificHumidity': ['LossDueToH2OInAir'], 'theoriticalAirRequired': ['LossDueToH2OInAir'], 'totalUnburntCarbonInAsh': ['LossDueToUnburntCarbon'], 'vaporPressure': ['LossDueToH2OInAir'], 'weightOfDryFlueGas': ['LossDueToDryFlueGas'], 'weightedAphInletTemp': ['LossDueToH2OInAir', 'LossDueToH2OInFuel', 'LossDueToH2InFuel', 'LossDueToDryFlueGas']}, 'saturationVaporPressure': 3.0234484115947686, 'sensibleHeatOfDryGas': 1396.4376573922075, 'sensibleHeatOfWater': 2629.6288, 'specificHumidity': 0.0, 'theoriticalAirRequired': 8.28929645264174, 'totalUnburntCarbonInAsh': 0.0031935417644509724, 'vaporPressure': 0.0, 'weightOfDryFlueGas': 0.4617079882824448, 'weightedAphInletTemp': 24.22, 'coalGCV': 5922.8218592555, 'hydrogen': 3.87355650441048, 'coalMoist': 11.5710558548511, 'carbon': 59.6727371390005, 'coalSulphur': 0.721959448746531, 'coalAsh': 12.9975148134525, 'nitrogen': 1.4480122094269, 'oxygen': 9.71516403011202, 'bedAshUnburntCarbon': 8.825556, 'flyAshUnburntCarbon': 1.74942744, 'type': 'type14', 'ambientAirPressurePascal': 0.968, 'ambientAirTemp': 24.22, 'ambientRelativeHumidityPRC': 0.0, 'aphFlueGasInletO2_A': 4.618, 'aphFlueGasInletO2_B': 5.557, 'aphFlueGasInletTemp': 287.895, 'aphFlueGasOutletO2_A': 7.92, 'aphFlueGasOutletO2_B': 5.502, 'aphFlueGasOutletTemp': 123.06, 'boilerSteamFlow': 457.756, 'ecoOutletCO2': 4.847, 'fdFlow': 412.129, 'fdOLTemp': 27.579, 'paFlow': 163.606, 'paOLTemp': 35.495, 'BLR_OFFSET': 0, 'Other_Losses_Plant_Specific_prc': 0, 'partialCombustionLoss': 0.01, 'LossUnaccounted': 0.25, 'airHumidityFactor': 0.016}, {'CondenserVacuum': -90.10539245605469, 'DripHph6Enthalpy': 682.9248785188961, 'DripHph6EnthalpyConstant': 0.36, 'DripHph7Enthalpy': 800.1235735180577, 'DripHph7EnthalpyConstant': -0.48, 'DripHph8Enthalpy': 939.1853869150829, 'DripTemperatureHph6': 161.7, 'DripTemperatureHph7': 188.5, 'DripTemperatureHph8': 219.1, 'ExtractionSteamFlowHph6': 17.39207742075273, 'ExtractionSteamFlowHph7': 26.377126744397984, 'ExtractionSteamFlowHph8': 29.601018233709087, 'ExtractionSteamHph5Enthalpy': 3187.159075294308, 'ExtractionSteamHph6Enthalpy': 3385.612694873628, 'ExtractionSteamHph6EnthalpyConstant': 0.43, 'ExtractionSteamHph7Enthalpy': 3030.7254335536068, 'ExtractionSteamHph7EnthalpyConstant': -0.43, 'ExtractionSteamHph8Enthalpy': 3149.5392043959705, 'ExtractionSteamHph8EnthalpyConstant': -0.5, 'ExtractionSteamPressureHph6': 1.073, 'ExtractionSteamPressureHph7': 2.047, 'ExtractionSteamPressureHph8': 3.675, 'ExtractionSteamTempHph6': 457.1, 'ExtractionSteamTempHph7': 303.7, 'ExtractionSteamTempHph8': 370.5, 'FWFinalPress': 12.636999130249023, 'FWFinalTemp': 244.0, 'FeedWaterFlow': 466.5550231933594, 'FeedWaterInletBeforeEcoEnthalpy': 1056.7634315599912, 'FeedWaterInletTempToHph6': 156.1, 'FeedWaterInletTempToHph7': 183.0, 'FeedWaterInletTempToHph8': 213.6, 'FeedWaterInletToHph6Enthalpy': 665.1193645428032, 'FeedWaterInletToHph6EnthalpyConstant': 0.19, 'FeedWaterInletToHph7Enthalpy': 781.6712993261535, 'FeedWaterInletToHph7EnthalpyConstant': 0.04, 'FeedWaterInletToHph8Enthalpy': 916.9858587303593, 'FeedWaterInletToHph8EnthalpyConstant': -0.14, 'FeedWaterOutletTempToHph8': 244.1, 'FeedWaterOutletToHph6Enthalpy': 781.4312993261535, 'FeedWaterOutletToHph6EnthalpyConstant': 0.2, 'FeedWaterOutletToHph7Enthalpy': 916.9858587303593, 'FeedWaterOutletToHph7EnthalpyConstant': -0.14, 'FeedWaterOutletToHph8Enthalpy': 1057.2238165308563, 'FeedWaterOutletToHph8EnthalpyConstant': -0.01, 'GlandSteamFlow_LeakOff_InterStageLeakage': 18.181, 'HptExhaustPressure': 1.7406033277511597, 'HptExhaustTemp': 304.3, 'HptSteamExhaustEnthalpy': 3040.9971056281047, 'HrhSteamFlow': 463.3708550218929, 'IptExhaustPressure': 550.3, 'IptExhaustTemp': 358.010986328125, 'IptInletSteamEnthalpy': 3556.580612994429, 'IptInletSteamPress': 1.939, 'IptInletSteamTemp': 539.859375, 'LptExhaustSteamTemp': 45.805938720703125, 'MakeUpWaterFlow': 0.0, 'RhSprayWater': 12.945927619934082, 'RhSprayWaterEnthalpy': 650.8081955267928, 'ShRhSprayWaterTemp': 152.70237731933594, 'ShSprayWater01': 32.98841094970703, 'ShSprayWater02': 0.0, 'ShSprayWaterEnthalpy': 650.8081955267928, 'SprayWaterEnthalpyConstant': 0.05, 'category': 'pressureInMpa', 'computedMainSteamFlow_computedFWFlow': 534.4693033646954, 'condensateFlow': 447.786, 'condensateInletHph5Enthalpy': 514.3816131554629, 'condensateInletTempHph5': 122.6, 'condensateInletWaterPress': 0.46884581446647644, 'condensateOutletHph5Enthalpy': 665.3725748388358, 'condensateTemp': 47.71, 'condenserCondensateInletTemp': 41.461265563964844, 'condenserCondensateOutletTemp': 33.0, 'condenserTTD': 2.9760023929949284, 'enthalpyFW': 1056.7634315599912, 'enthalpyMS': 3446.2836085812796, 'extractionSteamFlowHph5': 26.248008585769618, 'extractionSteamPressureHph5': 0.5615, 'extractionSteamTempHph5': 359.9, 'finalFeedWaterFlow_CalculatedFromCondensateFlow': 501.4808924149883, 'hotwellMakeUpFlow': 0.0, 'load': 149.37266540527344, 'steamFlowMS': 537.53, 'steamPressureMS': 12.362, 'steamTempMS': 538.0, 'totalShSprayWater': 32.98841094970703, 'turbineHeatRate': 2517.864081803404}]]
	

		for required_param in required_params:
			

			jsw_thr_dev_request_body = {}
			for k,v in required_param[0].items():
				jsw_thr_dev_request_body[k] = v
			for k,v in required_param[1].items():
				jsw_thr_dev_request_body[k] = v

			jsw_thr_dev_response = requests.post(effURL+"jsw_specific_thr_dev",json=jsw_thr_dev_request_body)
			if jsw_thr_dev_response.status_code ==200:
				jsw_thr_dev_response_content = json.loads(jsw_thr_dev_response.content)
				jsw_thr_dev_result.append(jsw_thr_dev_response_content)

				# print (required_params.index(required_param))
				# print(json.dumps(jsw_thr_dev_response_content, indent=4))
				# print ("\n\n\n")

				for k,v in mapping["turbineHeatRate"][0]["thr_outputs"].items():
					# print(k,v)
					param_dataTagId = v + suffixes[required_params.index(required_param)]
					if k not in mapping["turbineHeatRate"][0]["exclude_params"]:
						try:
							metricName = "6375e28c32ebf700068ac0aa_Turbine System_asset_manager"

							tagsDict = {}
							tagsDict["parameter"] = mapping["turbineHeatRate"][0]["thr_dev_params"][k]
							tagsDict["measureUnit"] = "kCal/kWHr"
							tagsDict["dataTagId"] = param_dataTagId
							tagsDict["calculationType"] = calc_type[required_params.index(required_param)]

							query_body_publish1 = [{"name" : metricName, "datapoints" : [[post_time, round(jsw_thr_dev_response_content[k], 4)]], "tags": tagsDict}]
							# print (query_body_publish1)
							qr.postDataPacket(query_body_publish1)
						except Exception as e:
							# This exception is intentional. Please dont ever comment this out in prod. 
							print (e)
							pass


					body_publish1 = [{"name" : param_dataTagId, "datapoints" : [[post_time, round(jsw_thr_dev_response_content[k], 4)]], "tags" : {"type": "raw"}}]                    
					res1 = qr.postDataPacket(body_publish1)
					# Publish results to topics
					client.publish(topic_line + param_dataTagId + '/r', json.dumps([{"r": body_publish1[0]["datapoints"][0][1], "t": body_publish1[0]["datapoints"][0][0]}]))
					client.publish("kairoswriteexternal",json.dumps(body_publish1))


				# print (zz)
				for k,v in jsw_thr_dev_response_content["relationship"].items():

					relatedTo = []
					for v2 in v:
						# print (v2)
						if v2 not in mapping["turbineHeatRate"][0]["exclude_params"]:
							relatedTo.append(mapping["turbineHeatRate"][0]["thr_dev_params"][v2])
					if relatedTo:
						metricName = "6375e28c32ebf700068ac0aa_Turbine System_asset_manager"
						tagsDict = {}
						tagsDict["dataTagId"] = "-"
						tagsDict["parameter"] = k
						tagsDict["measureUnit"] = "-"
						tagsDict["calculationType"] = calc_type[required_params.index(required_param)]
						tagsDict["relatedTo"] = json.dumps(relatedTo)
						# print (tagsDict)
						body_to_post = [{"name" : metricName, "datapoints" : [[post_time, round(jsw_thr_dev_response_content.get(k), 3)]], "tags": tagsDict}]
						# print(body_to_post)
						qr.postDataPacket(body_to_post)

		#why there is a different for loop here? coz here we want difference between des / bperf and actual - above its posting individual components but not the differences. 
		for k,v in mapping["turbineHeatRate"][0]["thr_outputs"].items():
			bperf_dev_val =  jsw_thr_dev_result[1][k] - jsw_thr_dev_result[0][k] #bperf
			des_dev_val = jsw_thr_dev_result[2][k] - jsw_thr_dev_result[0][k] #design

			param_dataTagId = v + "_bperf_dev"
			param_calc_type = "bperfDev"
			if k not in mapping["turbineHeatRate"][0]["exclude_params"]:
				try:
					metricName = "6375e28c32ebf700068ac0aa_Turbine System_asset_manager"
					tagsDict = {}
					tagsDict["parameter"] = mapping["turbineHeatRate"][0]["thr_dev_params"][k]
					tagsDict["measureUnit"] = "kCal/kWHr"
					tagsDict["dataTagId"] = param_dataTagId
					tagsDict["calculationType"] = param_calc_type

					query_body_publish1 = [{"name" : metricName, "datapoints" : [[post_time, round(bperf_dev_val, 4)]], "tags": tagsDict}]
					# print (query_body_publish1)
					qr.postDataPacket(query_body_publish1)
				except Exception as e:
					# This exception is intentional. Please dont ever comment this out in prod. 
					print (e)
					pass

			

			body_publish1 = [{"name" : param_dataTagId, "datapoints" : [[post_time, round(bperf_dev_val, 4)]], "tags" : {"type": "raw"}}]
			# print (body_publish1)         
			res1 = qr.postDataPacket(body_publish1)
			client.publish(topic_line+param_dataTagId + '/r', json.dumps([{"r": body_publish1[0]["datapoints"][0][1], "t": body_publish1[0]["datapoints"][0][0]}]))
			client.publish("kairoswriteexternal",json.dumps(body_publish1))


			param_dataTagId = v + "_des_dev"
			param_calc_type = "desDev"
			if k not in mapping["turbineHeatRate"][0]["exclude_params"]:
				tagsDict["dataTagId"] = param_dataTagId
				tagsDict["calculationType"] = param_calc_type

				query_body_publish1 = [{"name" : metricName, "datapoints" : [[post_time, round(des_dev_val,4)]], "tags": tagsDict}]
				qr.postDataPacket(query_body_publish1)

			body_publish1 = [{"name" : param_dataTagId, "datapoints" : [[post_time, round(des_dev_val, 4)]], "tags" : {"type": "raw"}}]   
			# print (body_publish1)                 
			res1 = qr.postDataPacket(body_publish1)
			client.publish(topic_line + param_dataTagId + '/r', json.dumps([{"r": body_publish1[0]["datapoints"][0][1], "t": body_publish1[0]["datapoints"][0][0]}]))
			client.publish("kairoswriteexternal",json.dumps(body_publish1))






	exec_end_time = time.time()
	total_exec_time_in_seconds = exec_end_time - exec_start_time
	print (unitId, total_exec_time_in_seconds)
	print ("PostTime", datetime.fromtimestamp(post_time / 1000))
	

def turbineSide():
	try:
		turbine_mapping_file_url = config["api"]["meta"]+'/units/'+unitId+'/boilerStressProfiles?filter={"where":{"type":"turbineSide"}}'
		res = requests.get(turbine_mapping_file_url)

		if res.status_code == 200:
			response_data = json.loads(res.content)
			config_data = response_data[0]["input"]
		else:
			print (res.status_code)
			print ("some issue in fetchign config for turbine side calcs or No Need of calcs itself. Presently, this is only applicable for HRD unit inside HRD DAta center, nowhere else")
			return 

		required_tags = []
		param_names = ["time"]
		for k,v in config_data.items():
			if isinstance(v, list):
				required_tags = required_tags + v
				param_names.append(k)
		print (len(required_tags), len(param_names))
		df = getLastValues(required_tags)
		df.columns = param_names
		# print (df)

		for k,v in config_data.items():
			if isinstance(v, list) ==  False:
				df[k] = v

		api_request_body = json.dumps(df.to_dict('records')[0])
		# print (api_request_body)
		# turbine_side_url = 'http://10.36.141.34:5077/efficiency/turbineSide'
		turbine_side_url = effURL+"turbineSide"
		api_response = requests.post(turbine_side_url, json=api_request_body)

		turbine_side_calcs = json.loads(api_response.content)

		for k,v in turbine_side_calcs.items():
			if k != "time":
				body_publish_01 = [{"name" : "HRD_3_"+str(k), "datapoints" : [[turbine_side_calcs["time"], round(v,4)]], "tags" : {"type": "raw"}}]
				# print (body_publish_01)
				res1 = qr.postDataPacket(body_publish_01)
	except Exception as e:
		print ("No Configs present turbine isentropic effs calculations")
		pass


	return ""


# -------------------------------------------------
# APScheduler error logging (safe, no override)
# -------------------------------------------------
aps_log = logging.getLogger('apscheduler.executors.default')
aps_log.setLevel(logging.ERROR)

fmt = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
handler = logging.StreamHandler()
handler.setFormatter(fmt)

if not aps_log.handlers:
	aps_log.addHandler(handler)



def should_run_as_cron(unit_id):
	cron_units = os.getenv("CRON_UNITS", "")
	cron_units = [u.strip() for u in cron_units.split(",") if u.strip()]
	return unit_id in cron_units



# ---- Initialize safely (NO logic modification) ----
_RUN_MODE = get_run_mode()


setup_logging(_RUN_MODE)
logging.info(f"Script started in {_RUN_MODE.upper()} mode")
# =

# Start scheduler

frequency = 300
if unitId == "660cdb2cb378100007f5ae71":
	frequency = 60

if _RUN_MODE == "cron":
	main()
	try:
		turbineSide()
	except Exception as e:
		logging.exception("Turbine Side Error")


# --------------- SERVER MODE ----------------
else:
	main()
	try:
		turbineSide()
	except Exception as e:
		logging.exception("Turbine Side Error")

	scheduler.add_job(main,'interval',seconds=frequency,misfire_grace_time=None,max_instances=2)

	scheduler.add_job(turbineSide,'interval',seconds=60,misfire_grace_time=None,max_instances=2)

	scheduler.start()

	while True:
		time.sleep(60)

# # Error Logging
# log = logging.getLogger('apscheduler.executors.default')
# log.setLevel(logging.ERROR)  # DEBUG
# fmt = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
# h = logging.StreamHandler()
# h.setFormatter(fmt)
# log.addHandler(h)
# logging.basicConfig()

# # Start scheduler

# frequency = 300
# if unitId == "660cdb2cb378100007f5ae71":
# 	frequency = 60

# main()
# try:
# 	turbineSide()
# except Exception as e:
# 	print ("Turbine Side Error :   ", e)
# scheduler.add_job(main, 'interval', seconds=frequency, misfire_grace_time=None, max_instances=2)
# scheduler.add_job(turbineSide, 'interval', seconds=60, misfire_grace_time=None, max_instances=2)
# scheduler.start()
# while True:
# 	time.sleep(60)
	
