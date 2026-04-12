# import gevent
# from gevent import monkey; monkey.patch_all()
from gevent import monkey as curious_george
curious_george.patch_all(thread=False, select=False)
import timeseries as ts
import grequests
import pandas as pd
import numpy as np
import pickle
import  sys
import app_config as cfg
import requests
import json
import time
import os
from flask import Flask, jsonify
import logging 
from flask import request
from flask import abort
from flask_cors import CORS
import datetime
from datetime import timedelta, datetime, date
from iapws import IAPWS97, iapws97
from logzero import logger
import math
import calendar
import inspect
import re 


#logging.basicConfig(level=logging.DEBUG)
import platform
version = platform.python_version().split(".")[0]
if version == "3":
	import app_config.app_config as cfg
	import timeseries.timeseries as ts
elif version == "2":
	import app_config as cfg
	import timeseries as ts

config = cfg.getconfig()
qr = ts.timeseriesquery()

app = Flask(__name__)

#app.logger.setLevel(logging.DEBUG)
try:
	config = cfg.getconfig()
	print(config["api"]["meta"])
	print("config loaded")
except:
	# time.sleep(30)
	sys.exit("config not loaded, existing")


# config = {
# 	"api": {
# 		"meta": 'https://pulse.thermaxglobal.com/exactapi',
# 		"query": 'https://pulse.thermaxglobal.com/kairosapi/api/v1/datapoints/query',
# 		"datapoints": "https://pulse.thermaxglobal.com/kairosapi/api/v1/datapoints"
# 	}
# }


#mappingFile Object Creation 

mapping_file_url = config["api"]["meta"]+'/boilerStressProfiles?filter={"where":{"type":"efficiencyMapping"}}'
res = requests.get(mapping_file_url)
mapping = {}
if res.status_code == 200 and len(res.json())!=0:
	mappings = res.json()
	for mapp in mappings:
		mapping[mapp["unitsId"]] = mapp["output"]
else:
	warning_mapping_file = "efficiency mapping files could not be fetched"
	print (warning_mapping_file)



class NpEncoder(json.JSONEncoder):
	def default(self, obj):
		if isinstance(obj, np.integer):
			return int(obj)
		if isinstance(obj, np.floating):
			return float(obj)
		if isinstance(obj, np.ndarray):
			return obj.tolist()
		return super(NpEncoder, self).default(obj)


def replace_with_description(data_dict, description_dict):
		updated_dict = {}

		for key, value in data_dict.items():
			if key in description_dict:
				updated_dict[description_dict[key]] = value
			else:
				updated_dict[key] = value

		return updated_dict


def add_hr_reconciliation(result_dict):

	# --- Extract HR values ---
	before = result_dict.get("before_turbine_heat_rate", 0.0)
	after  = result_dict.get("after_turbine_heat_rate", 0.0)

	# --- Actual change (After - Before) ---
	actual_diff = after - before

	# --- Accounted sum ---
	accounted_sum = sum(
		v for k, v in result_dict.items()
		if k not in [
			"before_turbine_heat_rate",
			"after_turbine_heat_rate"
		]
	)

	# --- Unaccounted ---
	result_dict["unaccountedLoss"] = (
		actual_diff - accounted_sum
	)

	# --- Move HR keys to end ---
	before_val = result_dict.pop("before_turbine_heat_rate", None)
	after_val  = result_dict.pop("after_turbine_heat_rate", None)

	if before_val is not None:
		result_dict["before_turbine_heat_rate"] = before_val

	if after_val is not None:
		result_dict["after_turbine_heat_rate"] = after_val

	return result_dict


def getPrefix(unitId):
	url = config["api"]["meta"]+'/ingestconfigs?filter={"where":{"unitsId":"'+unitId+'"}}'
	res= requests.get(url).json()
	return res[0]["TAG_PREFIX"]

def updateform(form):
	form=json.loads(form)
	id = form["id"]
	del form["id"]
	update_url = config["api"]["meta"]+'/forms/update?where={"id":"'+id+'"}'
	res = requests.post(update_url, json=form)
	return res.status_code

def getLastValuesTimeWise(taglist,startTime,endTime,end_absolute=0):
	# endTime = int((time.time()*1000) + (5.5*60*60*1000))
	taglist = list(filter(lambda tag: tag.lower() != "time", taglist))
	# print(taglist)
	if end_absolute !=0: 
		print("endabsolute is not 0")
		query = {"metrics": [],"start_absolute":startTime , "end_absolute":endTime }
		# print("query")
		# print(query)
	else:
		print("fetching relative 3 months data")
		query = {"metrics": [],"start_absolute":1,"end_absolute":endTime}
		#query={"metrics": [],"start_relative": {"value": "3", "unit": "months"}}
	for tag in taglist:
		query["metrics"].append({"name": tag,"aggregators":[{
			"name": "last","sampling": {"value": "3","unit": "months"},"align_sampling": True}],"order":"desc","limit":1})
	try: 
		res = requests.post(config['api']['query'],json=query).json()
		df = pd.DataFrame([{"time":res["queries"][0]["results"][0]["values"][0][0]}])
		# print(df)
		# print(":::::DF::::")
		for tag in res["queries"]:
			try:
				if tag["results"][0]["values"]: 
					if df.iloc[0,0] <  tag["results"][0]["values"][0][0]:
						df.iloc[0,0] =  tag["results"][0]["values"][0][0]
					df.loc[0,tag["results"][0]["name"]] = tag["results"][0]["values"][0][1]
				else:
					print("no values in database assigining it with 0 ")
					df.loc[0, tag["results"][0]["name"]] = 0

			except Exception as e:
				print("exception in innerlast value ",e)
				pass 
	except Exception as e:
		print("exception in last values",e)
		return pd.DataFrame()
	return df

def getHistoricValues(taglist, startTime, endTime):
	# print(taglist)
	tags, names = [], {}
	for i, j in taglist.items():
		tags.append(str(j[0]))
		names[str(j[0])] = str(i)
	queries = {}
	metrics = []
	var = { "tags": {}, "name": "","aggregators": [{"name": "filter", "filter_op": "lte","threshold": "0"}, {"name": "avg","sampling": {"value": "1","unit": "hours"},"align_start_time": True}],}
	#added filter because when avg of one hour is fetched somemight be 0 due to flow nature hence to avoid this in taking average
	def getdata_api(query):
		try:
			res = requests.post(config['api']['query'],json=query).json()
			# print(":::::::::")
			# print(config['api']['query'])
			# print("{}{}{}{}{}{}}{")
			
			merged_df = pd.DataFrame()

# Iterate over each query in the list of queries' results
			for query in res['queries']:
				tag = query['results'][0]['name']
				listOfList = query['results'][0]['values']
				
				# Construct a temporary DataFrame for the current query's data
				temp_df = pd.DataFrame(listOfList, columns=['time', tag])
				temp_df['time'] = pd.to_datetime(temp_df['time'], unit='ms', utc=True)
				temp_df.set_index('time', inplace=True)
				
				# Merge the temporary DataFrame with the merged result DataFrame
				if merged_df.empty:
					merged_df = temp_df
				else:
					merged_df = merged_df.merge(temp_df, how='outer', left_index=True, right_index=True)

# Reset the index of the merged DataFrame
			merged_df.reset_index(inplace=True)
			# df_list = []
			# for query in res['queries']:
			#     tag = query['results'][0]['name']
			#     listOfList = query['results'][0]['values']
			#     print("[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[")
			#     print(listOfList)
			#     print("["*100)
			#     time = [lists[0] for lists in listOfList]
			#     value = [lists[1] for lists in listOfList]
			#     df_temp = pd.DataFrame({"time": time, tag: value})
			#     df_list.append(df_temp)
			# df_with_most_data = max(df_list, key=len)
			# df = df_with_most_data.set_index('time')
			# for df_temp in df_list:
			#     if df_temp is not df_with_most_data:
			#         df_temp = df_temp.set_index('time')
			#         df = pd.merge(df, df_temp, left_index=True, right_index=True, how="outer")
			# df = df.reset_index()
			# print("merged df")
			# print(merged_df)
			return merged_df
		except json.JSONDecodeError as e:
			print(f"Error decoding JSON: {e}")
			return pd.DataFrame()

	for tag in tags:
		var["name"] = tag
		var_dummy = var.copy()
		metrics.append(var_dummy)
		queries["metrics"] = metrics
		queries["start_absolute"] = startTime
		queries["end_absolute"] = endTime
	result = getdata_api(queries)
	print("result")
	NanTags = result.columns[result.isna().all()].tolist()
	if NanTags:
		print("nantags", NanTags)
		nDf=getLastValuesTimeWise(NanTags, startTime, endTime)

	else:
		print("NanTags is empty, skipping further processing")
	if len(NanTags) != 0:
		if nDf.empty:
			print("nDf is empty, filling with zeros for NanTags")
			for tag in NanTags:
				result[str(tag)] = 0
		else:
			for tag in NanTags:
				print("tag", tag)
				if tag in nDf.columns:
					result[str(tag)] = nDf[str(tag)]

	# result.fillna(method="ffill",inplace=True)
	# result.fillna(method="bfill",inplace=True)
	# print(result)
	# pd.set_option('display.max_columns',None)
	result['time'] = pd.to_datetime(result['time'], unit='ms', utc=True).dt.tz_convert('Asia/Kolkata').dt.strftime('%d-%m-%Y %H:%M:%S')
	if (result.shape[1]!=0):
		result.rename(columns=names, inplace=True)

	return result


def fetch_tags(unitId):
	mapping = ""
	config = cfg.getconfig()[unitId]
	effURL = config['api']['efficiency']
	topic_line = "u/" + unitId + "/"
	mapping_file_url = config["api"]["meta"]+'/units/'+unitId+'/boilerStressProfiles?filter={"where":{"type":"efficiencyMapping"}}'
	res = requests.get(mapping_file_url)
	
	if res.status_code == 200 and len(res.json())!=0:
		mapping_file = res.json()[0]
		mapping = mapping_file["output"]
	
	tags = []
	for item in mapping["boilerEfficiency"]:
		for i, j in item['realtime'].items():
			if str(i) != "ambientAirTemp":
				tags.extend(j)

	if mapping.get("turbineHeatRate"):
		for item in mapping["turbineHeatRate"]:
			for i in item['realtime'].values():
				tags.extend(i)
	ld_tags = []
	print ("Tags:", len(tags))
	for tag in tags:
		url = config["api"]["meta"] + '/units/' + str(unitId) + '/tagmeta?filter={"where":{"dataTagId":"' + str(tag) + '"},"fields":["equipmentId"]}'
		res = requests.get(url)
		
		if (res.status_code == 200) and (len(res.json())):
			equipId = res.json()[0]["equipmentId"]
			url = config["api"]["meta"] + '/units/' + str(unitId) +'/equipment/' + str(equipId)
			res = requests.get(url)
		
			if res.status_code == 200 and len(res.json()):
				load = res.json()["equipmentLoad"]["loadTag"]
				ld_tags.append(load)
			else:
				print ("equipId data Unavailable:", url)
		
		else:
			print ("tagmeta Unavailable: ", url , tag)

	tags = tags + ld_tags
	tags = [tag[0] if type(tag)==list else tag for tag in tags]
	tags = list(set(tags))
	return tags

def uploadRefernceData(fileName):
	print(fileName)
	print(type(fileName))
	#path = os.path.join(os.path.dirname(os.path.realpath(__file__)),'../../processOutput/model_pipeline_results/')
	path = ""
	files = {'upload_file': open(str(path+fileName),'rb')}
	url=config['api']['meta']+"/attachments/test/upload"
	#url  = 'http://10.211.19.36:3071/exactapi/attachments/incidents/upload'
	#url = 'https://pulse.thermaxglobal.com/exactapi/attachments/incidents/'
	response = requests.post(url, files=files)
	print ("uploading")
	print (url)
	print ("+"*20)
	print("response",response)

	if(response.status_code==200):
		status ="success"
		print(path+fileName)
		#os.remove(str(path+fileName))
	else:
		status= (str(response.status_code) + str(response.content))
		print (response.status_code, response.content)
	return status

# fileName = "harsha.csv"
# df.to_csv(fileName)
# uploadTrainingResults(fileName)

def downloadReferenceData(fileName):
	url=config["api"]["meta"]+"/attachments/test/download/"+fileName
	with requests.get(url, stream=True) as r:
		r.raise_for_status()
		with open(fileName+'_read', 'wb') as f:
			for chunk in r.iter_content(chunk_size=8192):
				if chunk:
					f.write(chunk)
	with open(fileName+'_read', 'rb') as f1:
		dfRead = pd.read_csv(f1)
	print ("file created")
	#print(dfRead)
	return dfRead

def fetch_data(unitId):
	tags = fetch_tags(unitId)
	
	endTime = int(time.time()) * 1000
	year_span = 1
	print ("fetching " + str(year_span) + " years of data...")
	startTime = endTime - (1000 * 60 * 60 * 24 * 365 * year_span)

	try:
		qr = ts.timeseriesquery()
		qr.addMetrics(tags)
		qr.chooseTimeType("absolute",{"start_absolute":str(startTime), "end_absolute":str(endTime)})
		qr.addAggregators([{"name":"avg", "sampling_value":1,"sampling_unit":"hours"}])
		qr.submitQuery()
		qr.formatResultAsDF()
		df = qr.resultset["results"][0]["data"]
		
		print ("Data shape: ", df.shape)
		print ("Data available from: " + str(datetime.utcfromtimestamp(df.iloc[0]["time"] / 1000).strftime('%d %b %Y %H:%M %p')))
		print ("To: " + str(datetime.utcfromtimestamp(df.iloc[-1]["time"] / 1000).strftime('%d %b %Y %H:%M %p')))
		
		# try to use attachments API
		# ref file @TMXEIOTPRODAPP1:/space/es-master/src/bibhu/upload-api-test/upload.py
		#print "dataframe"
		#print df
		#df.to_csv("./efficiency-calculations/ref_data_" + str(unitId), index=False)
		df.to_csv("ref_data_" + str(unitId) + ".csv", index=False)
		uploadRefernceData("ref_data_" + str(unitId) + ".csv")
		os.remove("ref_data_" + str(unitId) + ".csv")
	
	except Exception as e:
		print ("Exception in Fetching, Unable to Fetch and Save Reference File")
		print (e)

def process_dataframe(df, weighted_avg_coal_cost, displayList):
	# Reset index and format time
	df.reset_index(drop=True, inplace=True)
	df['time'] = pd.to_datetime(df['time']).dt.strftime('%d-%m-%Y %H:%M:%S')
	
	# Calculations
	df["NetTgLoad"] = (df["TgLoad"] - (df["aux power"] / 24))
	df["DirectCost/KWh"] = (df["weightedLandingCost"] * df["directCoalflow"]) / (df["TgLoad"] * 1000)
	df["NetDirectCost/KWh"] = (df["weightedLandingCost"] * df["directCoalflow"]) / (df["NetTgLoad"] * 1000)
	df["InDirectCost/KWh"] = (df["weightedLandingCost"] * df["coalFlow"]) / (df["TgLoad"] * 1000)
	df["NetInDirectCost/KWh"] = (df["weightedLandingCost"] * df["coalFlow"]) / (df["NetTgLoad"] * 1000)
	
	df["correctedIndirectSteamCost"] = (weighted_avg_coal_cost * df['coalFlow']) / df['boilerSteamFlow']
	df["correctedSteamCost"] = (weighted_avg_coal_cost * df['directCoalflow']) / df['boilerSteamFlow']
	df["correctedDirectCost/KWh"] = (weighted_avg_coal_cost * df["directCoalflow"]) / (df["TgLoad"] * 1000)
	df["correctedNetDirectCost/KWh"] = (weighted_avg_coal_cost * df["directCoalflow"]) / (df["NetTgLoad"] * 1000)
	df["correctedInDirectCost/KWh"] = (weighted_avg_coal_cost * df["coalFlow"]) / (df["TgLoad"] * 1000)
	df["correctedNetInDirectCost/KWh"] = (weighted_avg_coal_cost * df["coalFlow"]) / (df["NetTgLoad"] * 1000)
	
	# Renaming and rounding
	df.rename(columns={'time': 'Date'}, inplace=True)
	columns_to_round = [col for col in df.columns if col != 'Date']
	df[columns_to_round] = df[columns_to_round].round(2)
	
	# Reorder columns
	remaining_columns = [col for col in df.columns if col not in displayList]
	new_columns_order = displayList + remaining_columns
	df_reordered = df[new_columns_order]
	
	# Column mapping
	prefix = 'inDirect'
	columns_to_check = ['coalFlow', 'costOfFuel', 'costPerUnitSteam']
	column_mapping = {col: prefix + col if col in columns_to_check else col for col in df_reordered.columns}
	df_reordered.rename(columns=column_mapping, inplace=True)
	
	# Print full DataFrame
	pd.set_option('display.max_columns', None)
	print(df_reordered)
	
	# Prepare data for further use
	columns = df_reordered.columns.tolist()
	data_values = [columns] + df_reordered.values.tolist()
	
	return  data_values        

# Fetch design values for real time values
@app.route('/efficiency/design', methods=['POST'])
def fetchDesign():
	designIndex = {}
	#config = cfg.getconfig()
	designObj = request.json
	unitId = designObj["unitId"]
	if (unitId== "62ff525f0053c325ccf27a1d"):
		print ("BATAAN UNIT")
	elif (unitId=="61c1818371c20d4a206a2e35"):
		print("JKLC_UNIT")
	load = float(designObj["load"])
	fields = ["designValues","dataTagId"]
	tagmeta_uri = config["api"]["meta"] + '/units/' + str(unitId) + '/tagmeta?filter={"where":'
	gres = []
	#rs  = [grequests.get(tagmeta_uri + json.dumps({"dataTagId" : str(value[0])}) + ',"fields":' + json.dumps(fields) + '}') for _, value in designObj["realtime"].items()] + [grequests.get(tagmeta_uri + json.dumps({"dataTagId" : str(value[0])}) + ',"fields":' + json.dumps(fields) + '}') for _, value in designObj["loi"].items()]
	for _, value in designObj["realtime"].items():
		gres.append(requests.get(tagmeta_uri + json.dumps({"dataTagId" : str(value[0])}) + ',"fields":' + json.dumps(fields) + '}'))
	# rs  = [grequests.get(tagmeta_uri + json.dumps({"dataTagId" : str(value[0])}) + ',"fields":' + json.dumps(fields) + '}') for _, value in designObj["realtime"].items()]

	# gres = grequests.map(rs)
	# assert(len(gres) == len(designObj["realtime"])) + len(designObj["loi"])
	# print ("$$$$$")
	# print (gres)
	# print ("$$$$$")
	
	for i in range(len(gres)):
		# print (i, gres[i].status_code, gres[i])
		if json.loads(gres[i].content):
			# print (json.loads(gres[i].content))
			des = json.loads(gres[i].content)[0].get("designValues")
			designIndex[str(json.loads(gres[i].content)[0].get("dataTagId"))] = des


	for k, v in designObj["realtime"].items():
		val = ""
		temp = designIndex.get(str(v[0]))
		if temp:
			for dv in temp["load"]:
				if ((load >= float(dv["lower"])) and (load < float(dv["upper"]))):
					try:
						val = float(dv["value"])
					except:
						pass
				
		try:
			designObj["realtime"][str(k)] = val if (val != "") else designObj["realtimeData"][str(k)]
		except:
			print (k, "error in getting design value\n\n")
			designObj["realtime"][str(k)] = np.nan

	''' 
	for k, v in designObj["loi"].items():
		val = ""
		temp = designIndex.get(str(v[0]))
		if temp:
			for dv in temp["load"]:
				if int(load) in range(int(dv["lower"]), int(dv["upper"])):
					val = float(dv["value"])

		designObj["loi"][str(k)] = val if (val != "") else designObj["realtimeData"][str(k)]
	'''
	del designIndex
	print ("*************")
	print (load)
	# print (json.dumps(designObj, indent=4))
	# print (zz)
	return dict(list(designObj["realtime"].items()) + list(designObj["loi"].items()))


# Fetch design values for real time values
#@app.route('/efficiency/design', methods=['POST'])
def fetchDesign1():
	global config
	config = cfg.getconfig()
	designObj = request.json
	unitId = designObj["unitId"]
	load = designObj["load"]
	fields = ["designValues","dataTagId"]
	tagmeta_uri = config["api"]["meta"] + '/units/' + str(unitId) + '/tagmeta?filter={"where":'
	rs  = [grequests.get(tagmeta_uri + json.dumps({"dataTagId" : str(value[0])}) + ',"fields":' + json.dumps(fields) + '}') for _, value in designObj["realtime"].items()] 
	gres = grequests.map(rs)
	assert(len(gres) == len(designObj["realtime"]))
	designIndex = {}
	for i in range(len(gres)):
		if json.loads(gres[i].content):
			des = json.loads(gres[i].content)[0].get("designValues")
			designIndex[str(json.loads(gres[i].content)[0].get("dataTagId"))] = des

	for k, v in designObj["realtime"].items():
		lr = designIndex.get(str(v[0]))
		'''
		if lr:
			val = ""
			for item in lr["load"]:
				if item["type"] == "HPIN":
					if load in range(int(item["lower"]), int(item["upper"])):
						val = float(item["value"]) if item["value"] != "" else None
			val = 0 if not val else val
			print(str(k), str(v[0]), val if val != "" else None)
			designObj["realtime"][str(k)] = val if val != "" else designObj["realtimeData"][str(k)]
			
		else:
		'''
		print(k, str(v[0]), None)
		designObj["realtime"][str(k)] = designObj["realtimeData"][str(k)]
		
	return designObj["realtime"]


# Function for best-achieved
@app.route('/efficiency/bestachieved', methods=['POST'])
def bestAchieved():
	print ("came to best Achieved")
	# print json.dumps(request.json, indent=4)
	bperfObj = request.json
	unitId = bperfObj["unitId"]
	load_tag = bperfObj["loadTag"]
	load = bperfObj["load"]
	
	#try to use attachments API
	# ref file @TMXEIOTPRODAPP1:/space/es-master/src/bibhu/upload-api-test/upload.py
	# ref_fl = "./efficiency-calculations/ref_data_" + str(unitId)
	
	if ((datetime.now().hour == 23) and
		(datetime.now().minute == 22)):
		
		fetch_data(unitId)
		print ("001")
	
	print ("002")
	try:        
		# ref_data = pd.read_csv(ref_fl)
		ref_data = downloadReferenceData("ref_data_" + str(unitId) + ".csv")
		print ("003")
	except Exception as e:
		print ("004")
		print (e)
		fetch_data(unitId)
		# ref_data = pd.read_csv(ref_fl)
		ref_data = downloadReferenceData("ref_data_" + str(unitId) + ".csv")
	print ("005")
	print (load_tag)
	print (load)
	print (ref_data)
	for k, v in bperfObj["realtime"].items():
		try:
			bperfObj["realtime"][str(k)] = round(ref_data[(ref_data[load_tag] >= (int(load) - 5)) & (ref_data[load_tag] <= (int(load) + 5))][str(v[0])].quantile(0.25), 3)
		except Exception as e:
			print (e)
			bperfObj["realtime"][str(k)] = np.nan
	# print bperfObj["realtime"]
	# del ref_data
	os.remove("ref_data_" + str(unitId) + ".csv_read")
	return bperfObj["realtime"]

# Function Proximate to ultimate
@app.route('/efficiency/proximatetoultimate', methods=['POST'])
def proximatetoultimate():
	print ("$$ Received  request in proximatetoultimate")
	res = request.json
	if "type" not in res:
		#print "res inside if"
		#print json.dumps(res,indent=4)
		return json.dumps({"error" : "line 255 ProximateToUltimate require 'type' in if condition for calculations","res":json.dumps(res)})

	else:
		if res["type"] == "type1":
			return proximateToUltimateType1(res)
		elif res["type"] == "type2":
			return proximateToUltimateType2(res)
		elif res["type"] == "type3":
			return proximateToUltimateType3(res)
		elif res["type"] == "type4":
			return proximateToUltimateType4(res)
		elif res["type"] == "type5":
			return proximateToUltimateType5(res)
		elif res["type"] == "type6":
			return proximateToUltimateType6(res)
		elif res["type"] == "type7":
			return proximateToUltimateType7(res)
		elif res["type"] == "type8":
			return proximateToUltimateType8(res)
		elif res["type"] == "type9":
			return proximateToUltimateType9(res)
		elif res["type"] == "type10":
			return proximateToUltimateType10(res)
		elif res["type"] == "type11":
			return proximateToUltimateType11(res)
		elif res["type"] == "type12":
			return proximateToUltimateType12(res)
		elif res["type"] == "type13":
			return proximateToUltimateType13(res)
		elif res["type"] == "type14":
			return proximateToUltimateType14(res)
		elif res["type"] == "type15":
			return proximateToUltimateType15(res)
		elif res["type"] == "type17":
			return proximateToUltimateType17(res)
		elif res["type"] == "type18":
			return proximateToUltimateType18(res)
		else:
			#print "res inside else"
			#print json.dumps(res,indent=4)
			return json.dumps({"error" : "line 283 ProximateToUltimate require 'type' for calculations",})
		

def proximateToUltimateType1(res):

	#res = request.json
	print ("response from type1")
	logger.info(res)
	for i in ["coalFC", "coalVM", "coalAsh", "coalMoist"]:
		if (i not in res):
			print ("error: " + str(i) + " missing or '0' found")
			return json.dumps({"error" : str(i) + " missing or '0' found"}), 400
	
	result = {
	"carbon" : (0.97 * res['coalFC']) + (0.7 * (res['coalVM'] + (0.1 * res['coalAsh']))-(res['coalMoist'] * (0.6 - (0.01 * res['coalMoist'])))),
	"hydrogen" : (0.036 * res['coalFC']) + (0.086 * ((res['coalVM']) - (0.1 * res['coalAsh']))) - (0.0035 * res['coalMoist'] * res['coalMoist'] *(1 - 0.02 * res['coalMoist'])),
	"nitrogen" : 2.1 - (0.02 * res['coalVM']),
	"coalSulphur" : 0.009 * (res['coalFC'] + res['coalVM'])
	}

	result['oxygen'] = 100 - result['carbon'] - result['hydrogen'] - result['coalSulphur'] - result['nitrogen'] - res['coalAsh'] - res['coalMoist']
	return result


def proximateToUltimateType2(res):
	print ("proximateToUltimateType2 responded")
	logger.info(res)
	for i in ["coalFC", "coalVM", "coalAsh", "coalMoist"]:
		if (i not in res) or (res[i] == 0):
			print ("error: " + str(i) + " missing or '0' found")
			return json.dumps({"error" : str(i) + " missing or '0' found"}), 400
	
	result = {
	"carbon" : (0.97 * res['coalFC']) + (0.7 * (res['coalVM'] + (0.1 * res['coalAsh']))-(res['coalMoist'] * (0.6 - (0.01 * res['coalMoist'])))),
	"hydrogen" : (0.036 * res['coalFC']) + (0.086 * ((res['coalVM']) - (0.1 * res['coalAsh']))) - (0.0035 * res['coalMoist'] * res['coalMoist'] *(1 - 0.02 * res['coalMoist'])),
	"nitrogen" : 2.1 - (0.02 * res['coalVM']),
	"coalSulphur" : 0.009 * (res['coalFC'] + res['coalVM'])
	}
	result["mineralMatter"] = res["coalAsh"] * 1.1
	result['oxygen'] = 100 - result['carbon'] - result['hydrogen'] - result['coalSulphur'] - result['nitrogen'] - result['mineralMatter'] - res['coalMoist']
	return result


def proximateToUltimateType3(res):
	#res = request.json
	print (res)
	for i in ["coalFC", "coalVM", "coalAsh", "coalMoist"]:
		if (i not in res) or (res[i] == 0):
			return json.dumps({"error" : str(i) + " missing or '0' found"}), 400
	
	result = {
	"carbon" : (0.97 * res['coalFC']) + (0.7 * (res['coalVM'] + (0.1 * res['coalAsh']))-(res['coalMoist'] * (0.6 - (0.01 * res['coalMoist'])))),
	"hydrogen" : (0.036 * res['coalFC']) + (0.086 * ((res['coalVM']) - (0.1 * res['coalAsh']))) - (0.0035 * res['coalMoist'] * res['coalMoist'] *(1 - 0.02 * res['coalMoist'])),
	"nitrogen" : 2.1 - (0.02 * res['coalVM']),
	"coalSulphur" : 0.009 * (res['coalFC'] + res['coalVM'])
	}

	result['oxygen'] = 100 - result['carbon'] - result['hydrogen'] - result['coalSulphur'] - result['nitrogen'] - res['coalAsh'] - res['coalMoist']
	return result


def proximateToUltimateType4(res):
	#res = request.json
	# print res
	for i in ["coalFC", "coalVM", "coalAsh", "coalMoist"]:
		if (i not in res) or (res[i] == 0):
			return json.dumps({"error" : str(i) + " missing or '0' found"}), 400
	
	result = {
	"carbon" : (0.97 * res['coalFC']) + (0.7 * (res['coalVM'] + (0.1 * res['coalAsh']))-(res['coalMoist'] * (0.6 - (0.01 * res['coalMoist'])))),
	"hydrogen" : (0.036 * res['coalFC']) + (0.086 * ((res['coalVM']) - (0.1 * res['coalAsh']))) - (0.0035 * res['coalMoist'] * res['coalMoist'] *(1 - 0.02 * res['coalMoist'])),
	"nitrogen" : 2.1 - (0.02 * res['coalVM']),
	"coalSulphur" : 0.009 * (res['coalFC'] + res['coalVM'])
	}

	result['oxygen'] = 100 - result['carbon'] - result['hydrogen'] - result['coalSulphur'] - result['nitrogen'] - res['coalAsh'] - res['coalMoist']
	return result


def proximateToUltimateType5(res):
	#res = request.json
	# print res
	for i in ["coalFC", "coalVM", "coalAsh", "coalMoist"]:
		if (i not in res) or (res[i] == 0):
			return json.dumps({"error" : str(i) + " missing or '0' found"}), 400
	
	result = {
	"carbon" : (0.97 * res['coalFC']) + (0.7 * (res['coalVM'] + (0.1 * res['coalAsh']))-(res['coalMoist'] * (0.6 - (0.01 * res['coalMoist'])))),
	"hydrogen" : (0.036 * res['coalFC']) + (0.086 * ((res['coalVM']) - (0.1 * res['coalAsh']))) - (0.0035 * res['coalMoist'] * res['coalMoist'] *(1 - 0.02 * res['coalMoist'])),
	"nitrogen" : 2.1 - (0.02 * res['coalVM']),
	"coalSulphur" : 0.009 * (res['coalFC'] + res['coalVM'])
	}

	# print "@@@@@@@@@@@@@"
	# print "Carbon, Hydrogen, Nitrogen, Oxy", result['carbon'], result['hydrogen'], result['nitrogen'], result['coalSulphur']
	result['oxygen'] = 100 - result['carbon'] - result['hydrogen'] - result['coalSulphur'] - result['nitrogen'] - res['coalAsh'] - res['coalMoist']
	return result


def proximateToUltimateType6(res):
	#res = request.json
	# print res
	for i in ["coalFC", "coalVM", "coalAsh", "coalMoist"]:
		if (i not in res) or (res[i] == 0):
			return json.dumps({"error" : str(i) + " missing or '0' found"}), 400
	
	result = {
	"carbon" : (0.97 * res['coalFC']) + (0.7 * (res['coalVM'] + (0.1 * res['coalAsh']))-(res['coalMoist'] * (0.6 - (0.01 * res['coalMoist'])))),
	"hydrogen" : (0.036 * res['coalFC']) + (0.086 * ((res['coalVM']) - (0.1 * res['coalAsh']))) - (0.0035 * res['coalMoist'] * res['coalMoist'] *(1 - 0.02 * res['coalMoist'])),
	"nitrogen" : 2.1 - (0.02 * res['coalVM']),
	"coalSulphur" : 0.009 * (res['coalFC'] + res['coalVM'])
	}

	result['oxygen'] = 100 - result['carbon'] - result['hydrogen'] - result['coalSulphur'] - result['nitrogen'] - res['coalAsh'] - res['coalMoist']
	return result


def proximateToUltimateType7(res):
	# print res
	for i in ["coalFC", "coalVM", "coalAsh", "coalMoist"]:
		if (i not in res) or (res[i] == 0):
			return json.dumps({"error" : str(i) + " missing or '0' found"}), 400

	result = proximateToUltimateType1(res)
	if 'coalSulphur' not in result or result['coalSulphur'] == 0:
		result['coalSulphur'] = 0.88
	result['oxygen'] = 100 - result['carbon'] - result['hydrogen'] - result['coalSulphur'] - result['nitrogen'] - res['coalAsh'] - res['coalMoist']
	return result

def proximateToUltimateType8(res):
	#res = request.json
	# print res
	for i in ["coalFC", "coalVM", "coalAsh", "coalMoist"]:
		if (i not in res):
			print ("error: " + str(i) + " missing or '0' found")
			return json.dumps({"error" : str(i) + " missing or '0' found"}), 400

	result = {
	"carbon" : (0.97 * res['coalFC']) + (0.7 * (res['coalVM'] + (0.1 * res['coalAsh']))-(res['coalMoist'] * (0.6 - (0.01 * res['coalMoist'])))),
	"hydrogen" : (0.036 * res['coalFC']) + (0.086 * ((res['coalVM']) - (0.1 * res['coalAsh']))) - (0.0035 * res['coalMoist'] * res['coalMoist'] *(1 - 0.02 * res['coalMoist'])),
	"nitrogen" : 2.1 - (0.02 * res['coalVM']),
	"coalSulphur" : 0.009 * (res['coalFC'] + res['coalVM'])
	}

	result['oxygen'] = 100 - result['carbon'] - result['hydrogen'] - result['coalSulphur'] - result['nitrogen'] - res['coalAsh'] - res['coalMoist']
	return result


def proximateToUltimateType9(res):
	#res = request.json
	# print res
	for i in ["coalFC", "coalVM", "coalAsh", "coalMoist"]:
		if (i not in res):
			# print "error: " + str(i) + " missing or '0' found"
			return json.dumps({"error" : str(i) + " missing or '0' found"}), 400

	result = {
	"carbon" : (0.97 * res['coalFC']) + (0.7 * (res['coalVM'] + (0.1 * res['coalAsh']))-(res['coalMoist'] * (0.6 - (0.01 * res['coalMoist'])))),
	"hydrogen" : (0.036 * res['coalFC']) + (0.086 * ((res['coalVM']) - (0.1 * res['coalAsh']))) - (0.0035 * res['coalMoist'] * res['coalMoist'] *(1 - 0.02 * res['coalMoist'])),
	"nitrogen" : 2.1 - (0.02 * res['coalVM']),
	"coalSulphur" : 0.009 * (res['coalFC'] + res['coalVM'])
	}

	result['oxygen'] = 100 - result['carbon'] - result['hydrogen'] - result['coalSulphur'] - result['nitrogen'] - res['coalAsh'] - res['coalMoist']
	return result


def proximateToUltimateType10(res):

	#res = request.json
	# print "response from type1"
	# print res
	for i in ["coalFC", "coalVM", "coalAsh", "coalMoist"]:
		if (i not in res):
			# print "error: " + str(i) + " missing or '0' found"
			return json.dumps({"error" : str(i) + " missing or '0' found"}), 400
	
	result = {
	
	"carbon" : (0.97 * res['coalFC']) + (0.7 * (res['coalVM'] + (0.1 * res['coalAsh']))-(res['coalMoist'] * (0.6 - (0.01 * res['coalMoist'])))),
	"hydrogen" : (0.036 * res['coalFC']) + (0.086 * ((res['coalVM']) - (0.1 * res['coalAsh']))) - (0.0035 * res['coalMoist'] * res['coalMoist'] *(1 - 0.02 * res['coalMoist'])),
	"nitrogen" : 2.1 - (0.02 * res['coalVM']),
	"coalSulphur" : 0.7,
	"mineral" : res['coalAsh'] * 1.1
	
	}

	result['oxygen'] = 100 - result['carbon'] - result['hydrogen'] - result['coalSulphur'] - result['nitrogen'] - result['mineral'] - res['coalMoist']
	return result

def proximateToUltimateType11(res):

	#res = request.json
	#print "response from type11"
	logger.info(res)
	for i in ["coalFC", "coalVM", "coalAsh", "coalMoist"]:
		if (i not in res):
			# print "error: " + str(i) + " missing or '0' found"
			return json.dumps({"error" : str(i) + " missing or '0' found"}), 400
	
	result = {
	"carbon" : (0.97 * res['coalFC']) + (0.7 * (res['coalVM'] + (0.1 * res['coalAsh']))-(res['coalMoist'] * (0.6 - (0.01 * res['coalMoist'])))),
	"hydrogen" : (0.036 * res['coalFC']) + (0.086 * ((res['coalVM']) - (0.1 * res['coalAsh']))) - (0.0035 * res['coalMoist'] * res['coalMoist'] *(1 - 0.02 * res['coalMoist'])),
	"nitrogen" : 2.1 - (0.02 * res['coalVM']),
	"coalSulphur" : 0.009 * (res['coalFC'] + res['coalVM'])
	}

	result['oxygen'] = 100 - result['carbon'] - result['hydrogen'] - result['coalSulphur'] - result['nitrogen'] - res['coalAsh'] - res['coalMoist']
	return result

def proximateToUltimateType12(res):
	#res = request.json
	print (res)
	for i in ["coalFC", "coalVM", "coalAsh", "coalMoist"]:
		if (i not in res):
			# print "error: " + str(i) + " missing or '0' found"
			return json.dumps({"error" : str(i) + " missing or '0' found"}), 400

	result = {
	"carbon" : (0.97 * res['coalFC']) + (0.7 * (res['coalVM'] + (0.1 * res['coalAsh']))-(res['coalMoist'] * (0.6 - (0.01 * res['coalMoist'])))),
	"hydrogen" : (0.036 * res['coalFC']) + (0.086 * ((res['coalVM']) - (0.1 * res['coalAsh']))) - (0.0035 * res['coalMoist'] * res['coalMoist'] *(1 - 0.02 * res['coalMoist'])),
	"nitrogen" : 2.1 - (0.02 * res['coalVM']),
	"coalSulphur" : 0.009 * (res['coalFC'] + res['coalVM'])
	}

	result['oxygen'] = 100 - result['carbon'] - result['hydrogen'] - result['coalSulphur'] - result['nitrogen'] - res['coalAsh'] - res['coalMoist']
	return result

def proximateToUltimateType13(res):
	res = request.json
	# print res
	for i in ["coalFC", "coalVM", "coalAsh", "coalMoist","coalGCV"]:
		if (i not in res):
			# print "error: " + str(i) + " missing or '0' found"
			return json.dumps({"error" : str(i) + " missing or '0' found"}), 400

	#parrs Formula 
	S=(0.009)*(res["coalFC"]+res["coalVM"])
	Z=res["coalMoist"]+1.1*res["coalAsh"]+0.1*S
	Qp=100*res["coalGCV"]*4.186/(100-Z)
	Vp=100*(res["coalVM"]-0.1*res["coalAsh"]-0.1*S)/(100-Z)
	Cp=0.0015782*Qp-0.2226*Vp+37.69
	Hp=0.0001707*Qp+0.0653*Vp-2.92


	result = {
	"carbon" : (1-0.01*Z)*Cp+0.05*res['coalAsh']-0.5*S,
	"hydrogen" : (1-0.01*Z)*Hp+0.01*res['coalAsh']-0.015*S,
	"coalSulphur" : 0.009 * (res['coalFC'] + res['coalVM']),
	"nitrogen"  :  2.1-0.012*res['coalVM']



	}

	result['oxygen'] = 100 - result['carbon'] - result['hydrogen'] - result['coalSulphur'] - result['nitrogen'] - res['coalAsh'] - res['coalMoist']
	return result

def proximateToUltimateType14(res):
	#res = request.json
	print (res)
	for i in ["coalFC", "coalVM", "coalAsh", "coalMoist"]:
		if (i not in res):
			# print "error: " + str(i) + " missing or '0' found"
			return json.dumps({"error" : str(i) + " missing or '0' found"}), 400

	result = {
	"carbon" : (0.97 * res['coalFC']) + (0.7 * (res['coalVM'] + (0.1 * res['coalAsh']))-(res['coalMoist'] * (0.6 - (0.01 * res['coalMoist'])))),
	"hydrogen" : (0.036 * res['coalFC']) + (0.086 * ((res['coalVM']) - (0.1 * res['coalAsh']))) - (0.0035 * res['coalMoist'] * res['coalMoist'] *(1 - 0.02 * res['coalMoist'])),
	"nitrogen" : 2.1 - (0.02 * res['coalVM']),
	"coalSulphur" : 0.009 * (res['coalFC'] + res['coalVM'])
	}

	result['oxygen'] = 100 - result['carbon'] - result['hydrogen'] - result['coalSulphur'] - result['nitrogen'] - res['coalAsh'] - res['coalMoist']
	return result

def proximateToUltimateType15(res):
	#res = request.json
	print (res)
	for i in ["coalFC", "coalVM", "coalAsh", "coalMoist"]:
		if (i not in res) or (res[i] == 0):
			return json.dumps({"error" : str(i) + " missing or '0' found"}), 400
	
	result = {
	"carbon" : (0.97 * res['coalFC']) + (0.7 * (res['coalVM'] + (0.1 * res['coalAsh']))-(res['coalMoist'] * (0.6 - (0.01 * res['coalMoist'])))),
	"hydrogen" : (0.036 * res['coalFC']) + (0.086 * ((res['coalVM']) - (0.1 * res['coalAsh']))) - (0.0035 * res['coalMoist'] * res['coalMoist'] *(1 - 0.02 * res['coalMoist'])),
	"nitrogen" : 2.1 - (0.02 * res['coalVM']),
	"coalSulphur" : 0.009 * (res['coalFC'] + res['coalVM'])
	}

	result['oxygen'] = 100 - result['carbon'] - result['hydrogen'] - result['coalSulphur'] - result['nitrogen'] - res['coalAsh'] - res['coalMoist']
	return result

def proximateToUltimateType17(res):
	#res = request.json
	print (res)
	for i in ["coalFC", "coalVM", "coalAsh", "coalMoist"]:
		if (i not in res) or (res[i] == 0):
			return json.dumps({"error" : str(i) + " missing or '0' found"}), 400
	
	result = {
	"carbon" : (0.97 * res['coalFC']) + (0.7 * (res['coalVM'] + (0.1 * res['coalAsh']))-(res['coalMoist'] * (0.6 - (0.01 * res['coalMoist'])))),
	"hydrogen" : (0.036 * res['coalFC']) + (0.086 * ((res['coalVM']) - (0.1 * res['coalAsh']))) - (0.0035 * res['coalMoist'] * res['coalMoist'] *(1 - 0.02 * res['coalMoist'])),
	"nitrogen" : 2.1 - (0.02 * res['coalVM']),
	"coalSulphur" : 0.009 * (res['coalFC'] + res['coalVM'])
	}

	result['oxygen'] = 100 - result['carbon'] - result['hydrogen'] - result['coalSulphur'] - result['nitrogen'] - res['coalAsh'] - res['coalMoist']
	return result

def proximateToUltimateType18(res):
	#res = request.json
	# print res
	for i in ["coalFC", "coalVM", "coalAsh", "coalMoist"]:
		if (i not in res):
			# print "error: " + str(i) + " missing or '0' found"
			return json.dumps({"error" : str(i) + " missing or '0' found"}), 400

	result = {
	"carbon" : (0.97 * res['coalFC']) + (0.7 * (res['coalVM'] + (0.1 * res['coalAsh']))-(res['coalMoist'] * (0.6 - (0.01 * res['coalMoist'])))),
	"hydrogen" : (0.036 * res['coalFC']) + (0.086 * ((res['coalVM']) - (0.1 * res['coalAsh']))) - (0.0035 * res['coalMoist'] * res['coalMoist'] *(1 - 0.02 * res['coalMoist'])),
	"nitrogen" : 2.1 - (0.02 * res['coalVM']),
	"coalSulphur" : 0.009 * (res['coalFC'] + res['coalVM'])
	}

	result['oxygen'] = 100 - result['carbon'] - result['hydrogen'] - result['coalSulphur'] - result['nitrogen'] - res['coalAsh'] - res['coalMoist']
	return result
	
proximatetoultimate_index = {"type1" : proximateToUltimateType1, 
					"type2" : proximateToUltimateType2, 
					"type3" : proximateToUltimateType3, 
					"type4" : proximateToUltimateType4, 
					"type5" : proximateToUltimateType5, 
					"type6" : proximateToUltimateType6, 
					"type7" : proximateToUltimateType7, 
					"type8" : proximateToUltimateType8, 
					"type9" : proximateToUltimateType9,
					"type10" : proximateToUltimateType10,
					"type11" :proximateToUltimateType11,
					"type12" :proximateToUltimateType12,
					"type13" :proximateToUltimateType13,
					"type14" :proximateToUltimateType14,
					"type15" :proximateToUltimateType15,
					"type17" :proximateToUltimateType17,
					"type18" :proximateToUltimateType18
					}


# Function for AFBC type1
@app.route('/efficiency/boiler', methods=['POST'])
def boilerEfficiency():
	res = request.json
	# print "in effBOilertype, ********"
	# print res
	if "type" not in res:
		return json.dumps({"error" : "Boiler efficiency loss type required for efficiency calculations"}), 400
	else:
		if res["type"] == "type1":
			return boilerEfficiencyType1(res)
		elif res["type"] == "type2":
			res = boilerEfficiencyType2(res)
			return get_relationship_between_input_output(boilerEfficiencyType2, res)
		elif res["type"] == "type3":
			return boilerEfficiencyType3(res)
		elif res["type"] == "type4":
			return boilerEfficiencyType4(res)
		elif res["type"] == "type5":
			return boilerEfficiencyType5(res)
		elif res["type"] == "type6":
			res = boilerEfficiencyType6(res) 
			return get_relationship_between_input_output(boilerEfficiencyType6, res)
		elif res["type"] == "type7":
			return boilerEfficiencyType7(res)
		elif res["type"] == "type8":
			return boilerEfficiencyType8(res)
		elif res["type"] == "type9":
			return boilerEfficiencyType9(res)
		elif res["type"] == "type10":
			return boilerEfficiencyType10(res)
		elif res["type"] == "type11":
			res = boilerEfficiencyType11(res) 
			return get_relationship_between_input_output(boilerEfficiencyType11, res)
			# return boilerEfficiencyType11(res)

		elif res["type"] == "type12":
			res = boilerEfficiencyType12(res) 
			return get_relationship_between_input_output(boilerEfficiencyType12, res)
		elif res["type"] == "type13":
			res = boilerEfficiencyType13(res) 
			return get_relationship_between_input_output(boilerEfficiencyType13, res) 
		elif res["type"] == "type14":
			res = boilerEfficiencyType14(res) 
			return get_relationship_between_input_output(boilerEfficiencyType14, res)
		elif res["type"] == "type15":
			res = boilerEfficiencyType15(res) 
		elif res["type"] == "type16":
			res = boilerEfficiencyType16(res) 
		elif res["type"] == "type17":
			res = boilerEfficiencyType17(res) 
			return get_relationship_between_input_output(boilerEfficiencyType17, res)
		elif res["type"] == "type18":
			return boilerEfficiencyType18(res)
		else:
			return json.dumps({"error" : "Boiler efficiency loss type unavailable for efficiency calculations"}), 400


def get_relationship_between_input_output(function_name, boiler_eff_calcs):
	funcString = inspect.getsource(function_name)
	to_reverse_string = []
	for line in funcString.splitlines():
		# print (line)
		if (line) and (line.strip()
		) and ("def" not in line) and (line.strip()[0] != "#"):
			pLine = line.replace("result", "res")
			to_reverse_string.append(pLine.strip())
	# print (to_reverse_string)
	graph = {}
	reversed_function = to_reverse_string[::-1]
	# print (reversed_function)
	for line in reversed_function:
		if "=" in line:
			lhs = line.split("=")[0]
			rhs = line.split("=")[1]
			count = 0
			lhsWord = ""
			rhsWord = ""
			for letter in lhs:
				if letter == '"':
					count = count + 1
				if count % 2 == 0:
					dontAppend = 0
				else:
					lhsWord = lhsWord + letter
			for letter in rhs:
				if letter == '"':
					count = count + 1
				if count % 2 == 0:
					dontAppend = 0
				else:
					rhsWord = rhsWord + letter
			# print (rhsWord, lhsWord)
			depends = rhsWord.split('"')
			notDepends = lhsWord.split('"')
			depends = list(set([dep for dep in depends if dep]))
			notDepends = list(set([dep for dep in notDepends if dep]))
			# print (depends, notDepends, "depends")
			#below calcs handles the relationship part between inputs outputs for boiler efficiency std calcs 
			for nd in notDepends:
				if ("oss" in nd) and ("otal" not in nd):
					if nd not in graph.keys():
						if depends:
							graph[nd] = depends
				else:
					for k,v in graph.items():
						for v2 in v:
							if nd == v2:
								# print(nd, v2, depends)
								graph[k] = graph[k] + depends
								graph[k] = list(set(graph[k]))
			#below logic handles the relationship part between input outputs for jsw specific thr calcs 
			for nd in notDepends:
				if ("thr_dev" in nd) and ("gross_heat_rate" not in nd):
					if nd not in graph.keys():
						if depends:
							graph[nd] = depends
				else:
					for k,v in graph.items():
						for v2 in v:
							if nd == v2:
								# print(nd, v2, depends)
								graph[k] = graph[k] + depends
								graph[k] = list(set(graph[k]))
			
	requiredGraph = {}
	for k,v in graph.items():
		for v2 in v:
			if v2 not in requiredGraph.keys():
				requiredGraph[v2] = []
			requiredGraph[v2].append(k)
	# print (json.dumps(requiredGraph, indent=4))
	boiler_eff_calcs["relationship"] = requiredGraph 
	return boiler_eff_calcs



def boilerEfficiencyType1(res):
	# print "***********RES*************"
	# print json.dumps(res, indent=4)
	# print "***", "flyAshUnburntCarbon" in res
	# print " **", "bedAshUnburntCarbon" in res
	for i in ["carbon", "hydrogen", "coalSulphur", "oxygen", "aphFlueGasOutletO2", "coalMoist", "aphFlueGasOutletTemp", "ambientAirTemp", "coalGCV","coalAsh","airHumidityFactor", "LossUnaccounted", "LossDueToRadiation", "flyAshUnburntCarbon", "bedAshUnburntCarbon"]:
		if i not in res:
			# print "this is missing********: ", str(i)
			return json.dumps({"error" : str(i) + " missing"}), 400
		
	result = {
		'TheoAirRequired' : 0.116 * res['carbon'] + 0.348 * res['hydrogen'] + 0.0435 * res['coalSulphur'] - 0.0435 * res['oxygen'],
		'ExcessAir' : (res['aphFlueGasOutletO2'] * 100) / (21 - res['aphFlueGasOutletO2']),
		'LossDueToH2OInFuel' : res['coalMoist'] * (584 + 0.45 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp'])) / res['coalGCV'],
		'LossDueToH2InFuel' : 8.937 * (584 + 0.45 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp'])) * res['hydrogen'] / res['coalGCV'],
		
		'LossBedAshUBC' : (((res["coalAsh"] / 100) * 0.15 * (res["bedAshUnburntCarbon"]) * 8080) / (100 - res["bedAshUnburntCarbon"])) * 100 / res['coalGCV'],
		'LossFlyAshUBC' : (((res["coalAsh"] / 100) * 0.85 * (res["flyAshUnburntCarbon"]) * 8080) / (100 - res["flyAshUnburntCarbon"])) * 100 / res['coalGCV'],
		'LossSensibleBedAsh' :  ((res["coalAsh"]  / 100) * 0.15 * 0.22) * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp']) * 100 / res['coalGCV'],
		'LossSensibleFlyAsh' : ((res["coalAsh"]  / 100) * 0.85 * 0.22) * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp']) * 100 / res['coalGCV'],
		'LossDueToRadiation' : res['LossDueToRadiation'],
		'LossUnaccounted' : res['LossUnaccounted'],
	}
	
	result['ActualAirSupplied'] = (1 + result['ExcessAir'] / 100) *  result['TheoAirRequired']
	# print "loss cal: ", res['airHumidityFactor'], result['ActualAirSupplied'], res['aphFlueGasOutletTemp'], res['ambientAirTemp']
	result['LossDueToH2OInAir'] = res['airHumidityFactor'] * result['ActualAirSupplied'] * 0.45 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp']) * 100 / res['coalGCV']
	
	result['massofDryFlueGas'] = (res['carbon'] * 44 / 12 + res['coalSulphur'] * 64 / 32 + res['nitrogen'] + result['ActualAirSupplied'] * 77 + (result['ActualAirSupplied'] - result['TheoAirRequired']) * 23) / 100
	result['LossDueToDryFlueGas'] = result['massofDryFlueGas'] * 0.23 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp']) * 100 / res['coalGCV']
	# print result['massofDryFlueGas'], (res['aphFlueGasOutletTemp'] - res['ambientAirTemp']) * 100, res['coalGCV']
	result['LossTotal'] =  result['LossDueToDryFlueGas'] + result['LossDueToH2OInFuel'] + result['LossDueToH2InFuel'] + result['LossDueToH2OInAir'] + result['LossBedAshUBC'] + result['LossFlyAshUBC'] +result['LossSensibleBedAsh'] +result['LossSensibleFlyAsh'] +result['LossUnaccounted'] + result['LossDueToRadiation']
	result['boilerEfficiency'] = 100 - result['LossTotal']
	# print result['boilerEfficiency']

	return result
	'''
	if result['boilerEfficiency'] < 95:
		return result
	else:
		return json.dumps({"error" : "Boiler efficiency is above 95" + str(result['boilerEfficiency'])}), 400
	'''


def boilerEfficiencyType2(res):
	result = {}
	result["LossESPAshUBC"] = res["coalAsh"] * 65 / 100 * res["espAshUnburntCarbon"] * 8077 / (100 * res["coalGCV"])
	result["LossBottomAshUBC"] = res["coalAsh"] * 5 / 100 * res["bedAshUnburntCarbon"] * 8077 / (100 * res["coalGCV"])
	if "cycloneAshUnburntCarbon" in res:
		result["LossCycloneAshUBC"] = res["coalAsh"] * 25 / 100 * res["cycloneAshUnburntCarbon"] * 8077 / (100 * res["coalGCV"])
		result["LossAPHAshUBC"] = res["coalAsh"] * 5 / 100 * res["aphAshUnburntCarbon"] * 8077 / (100 * res["coalGCV"])
	result["LossESPAshSensible"] = res["coalAsh"] * 65 / 10000 * 0.23 * (res["aphFlueGasOutletTemp"] - res["ambientAirTemp"]) * 100 / res["coalGCV"]
	result["LossBottomAshSensible"] = res["coalAsh"] * 5 / 10000 * 0.23 * (res["bedAshTemp"] - res["ambientAirTemp"]) * 100 / res["coalGCV"]
	result["LossCycloneAshSensible"] = res["coalAsh"] * 25 / 10000 * 0.23 * (res["cycloneAshTemp"] - res["ambientAirTemp"]) * 100 / res["coalGCV"]
	result["LossAPHAshSensible"] = res["coalAsh"] * 5 / 10000 * 0.23 * (res["aphFlueGasOutletTemp"] - res["ambientAirTemp"]) * 100 / res["coalGCV"]
	result["LossDueToH2InFuel"] = 8.937 * (584 + 0.45 * (res["aphFlueGasOutletTemp"] - res["ambientAirTemp"])) * res["hydrogen"] / res["coalGCV"]
	result["LossDueToH2OInFuel"] = res["coalMoist"] * (584 + 0.45 * (res["aphFlueGasOutletTemp"] - res["ambientAirTemp"])) / res["coalGCV"]
	result["LossDueToRadiation"] = res["lossDueToRadiation"]
	result["LossDueToPartialCombustion"] = res["partialCombustionLoss"]
	result["LossPlantSpecific"] = res["plantSpecificLoss"]
	result["TheoAirRequired"] = 0.116 * res["carbon"] + 0.348 * res["hydrogen"] + 0.0435 * res["coalSulphur"] - 0.0435 * res["oxygen"]
	result["aphFlueGasOutletO2"] = res["aphFlueGasOutletO2"] + res["airIngressConstant"]
	result["ExcessAir"] = result["aphFlueGasOutletO2"] * 100 / (21 - result["aphFlueGasOutletO2"])
	result["ActualAirSupplied"] = (1 + result["ExcessAir"] / 100) * result["TheoAirRequired"]
	result["massofDryFlueGas"] = (res["carbon"] * 44 / 12 + res["coalSulphur"] * 64 / 32 + res["nitrogen"] + result["ActualAirSupplied"] * 77 + (result["ActualAirSupplied"] - result["TheoAirRequired"]) * 23) / 100
	result["LossDueToH2OInAir"] = res["airHumidityFactor"] * result["ActualAirSupplied"] * 0.45 * (res["aphFlueGasOutletTemp"] - res["ambientAirTemp"]) * 100 / res["coalGCV"]
	result["LossDueToDryFlueGas"] = result["massofDryFlueGas"] * 0.24 * (res["aphFlueGasOutletTemp"] - res["ambientAirTemp"]) * 100 / res["coalGCV"]
	if "cycloneAshUnburntCarbon" in res:
		result["LossTotalUBC"] = result["LossESPAshUBC"] + result["LossBottomAshUBC"] + result["LossCycloneAshUBC"] + result["LossAPHAshUBC"]
	else:
		result["LossTotalUBC"] = result["LossESPAshUBC"] + result["LossBottomAshUBC"]


	result["LossTotalSensible"] = result["LossESPAshSensible"] + result["LossBottomAshSensible"] + result["LossCycloneAshSensible"] + result["LossAPHAshSensible"]
	result["LossTotal"] = result["LossTotalUBC"] + result["LossTotalSensible"] + result["LossDueToDryFlueGas"] + result["LossDueToH2OInFuel"] + result["LossDueToH2InFuel"] + result["LossDueToH2OInAir"] + result["LossDueToPartialCombustion"] + result["LossPlantSpecific"] + res["lossDueToRadiation"]
	result["boilerEfficiency"] = 100 - result["LossTotal"]
	return result


def boilerEfficiencyType3(res):
	# print json.dumps(res, indent=4)
	# print "***", "flyAshUnburntCarbon" in res
	# print " **", "bedAshUnburntCarbon" in res
	for i in ["carbon", "hydrogen", "coalSulphur", "oxygen", "aphFlueGasOutletO2", "coalMoist", "aphFlueGasOutletTemp", "ambientAirTemp", "coalGCV","coalAsh","airHumidityFactor", "LossUnaccounted", "LossDueToRadiation", "flyAshUnburntCarbon", "bedAshUnburntCarbon"]:
		if i not in res:
			return json.dumps({"error" : str(i) + " missing"}), 400
	
	
	result = {
		'TheoAirRequired' : 0.116 * res['carbon'] + 0.348 * res['hydrogen'] + 0.0435 * res['coalSulphur'] - 0.0435 * res['oxygen'],
		'ExcessAir' : (res['aphFlueGasOutletO2'] * 100) / (21 - res['aphFlueGasOutletO2']),
		'LossDueToH2OInFuel' : res['coalMoist'] * (584 + 0.45 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp'])) / res['coalGCV'],
		'LossDueToH2InFuel' : 8.937 * (584 + 0.45 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp'])) * res['hydrogen'] / res['coalGCV'],

		
		'LossBedAshUBC' :  res['coalAsh'] * 10 / 100 * res['bedAshUnburntCarbon'] * 8080 / (100 * res['coalGCV']),
		'LossFlyAshUBC' :  res['coalAsh'] * 90 / 100 * res['flyAshUnburntCarbon'] * 8080 / (100 * res['coalGCV']),
		
		'LossDueToRadiation' : res['LossDueToRadiation'],
		'LossUnaccounted' : res['LossUnaccounted'],
	}
	# print "$$$$$$$$$$$$$$$$$$$ Values here: ", res['coalAsh'], res['flyAshUnburntCarbon'], res['coalGCV'], result['LossFlyAshUBC']
	
	result['LossFlueGasUBC'] = res['COInFlueGasPPM'] * 28 * 5654 * 100 / ((10 ** 6) *  res['coalGCV'])
	result['ActualAirSupplied'] = (1 + result['ExcessAir'] / 100) *  result['TheoAirRequired']
	# print "loss cal: ", res['airHumidityFactor'], result['ActualAirSupplied'], res['aphFlueGasOutletTemp'], res['ambientAirTemp']
	result['LossDueToH2OInAir'] = res['airHumidityFactor'] * result['ActualAirSupplied'] * 0.45 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp']) * 100 / res['coalGCV']
	
	result['massofDryFlueGas'] = (res['carbon'] * 44 / 12 + res['coalSulphur'] * 64 / 32 + res['nitrogen'] + result['ActualAirSupplied'] * 77 + (result['ActualAirSupplied'] - result['TheoAirRequired']) * 23) / 100
	result['LossDueToDryFlueGas'] = result['massofDryFlueGas'] * 0.24 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp']) * 100 / res['coalGCV']
	result['LossTotal'] =  result['LossDueToDryFlueGas'] + result['LossDueToH2OInFuel'] + result['LossDueToH2InFuel'] + result['LossDueToH2OInAir'] + result['LossBedAshUBC'] + result['LossFlyAshUBC'] +result['LossUnaccounted'] + result['LossDueToRadiation'] + result['LossFlueGasUBC']
	result['boilerEfficiency'] = 100 - result['LossTotal']
	# print json.dumps(result, indent=4)
	return result


def boilerEfficiencyType4(res):

	for i in []:
		if i not in res:
			return json.dumps({"error" : str(i) + " missing"}), 400
	
	result = {
		'TheoAirRequired' : 0.116 * res['carbon'] + 0.03975 * res['hydrogen'] + 0.0435 * res['coalSulphur'] - 0.03975 * res['oxygen'],
		'ExcessAir' : (res['aphFlueGasOutletO2'] * 100) / (21 - res['aphFlueGasOutletO2']),
		'LossDueToH2OInFuel' : (res['coalMoist'] * (584 + 0.45 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp'])) / res['coalGCV']),
		'LossDueToH2InFuel' : (9 * (584 + 0.45 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp'])) * res['hydrogen'] / res['coalGCV']),
		'LossFlueGasUBC' : (res["COPerInFlueGas"] * res['carbon'] / (res["COPerInFlueGas"] + res["CO2PerInFlueGas"])) * (5744/res['coalGCV']) * 100,
		'LossDueToRadiation' : res['LossDueToRadiation'],
		'LossBedAshUBC' :  res['coalAsh'] * 10 / 100 * res['bedAshUnburntCarbon'] * 8080 / (100 * res['coalGCV']),
		'LossFlyAshUBC' :  res['coalAsh'] * 90 / 100 * res['flyAshUnburntCarbon'] * 8080 / (100 * res['coalGCV'])
	}
	
	result['ActualAirSupplied'] = (1 + result['ExcessAir'] / 100) *  result['TheoAirRequired']
	result['massofDryFlueGas'] = (res['carbon'] * 44 / 12 + res['nitrogen'] + result['ActualAirSupplied'] * 77 + (result['ActualAirSupplied'] - result['TheoAirRequired']) * 23) / 100
	result['LossDueToDryFlueGas'] = result['massofDryFlueGas'] * 0.23 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp']) * 100 / res['coalGCV']
	result['LossDueToH2OInAir'] = res['airHumidityFactor'] * result['ActualAirSupplied'] * 0.45 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp']) * 100 / res['coalGCV']
	result['LossTotal'] =  result['LossDueToDryFlueGas'] + result['LossDueToH2OInFuel'] + result['LossDueToH2InFuel'] + result['LossDueToH2OInAir'] + result['LossBedAshUBC'] + result['LossFlyAshUBC'] +result['LossFlueGasUBC'] + result['LossDueToRadiation']


def boilerEfficiencyType5(res):
	for i in ['carbon', 'hydrogen', 'coalSulphur', 'oxygen', 'aphFlueGasOutletO2', 'aphFlueGasOutletO2', 'ambientAirTemp', 'coalGCV', 'partialCombustionLoss', 'lossDueToRadiation', 'espAshUnburntCarbon']:
		if i not in res:
			# print "error: " + str(i) + " missing"
			return json.dumps({"error" : str(i) + " missing"}), 400

	res['bedAshUnburntCarbon'] = 0.8
	result = {

		'TheoAirRequired' : ((0.116 * res['carbon']) + (0.348 * res['hydrogen']) + (0.0435 * res['coalSulphur']) - (0.0435 * res['oxygen'])),
		'ExcessAir' : (res['aphFlueGasOutletO2'] * 100) / (21 - res['aphFlueGasOutletO2']),
		'LossDueToH2InFuel' : (9 * (584 + 0.45 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp'])) * res['hydrogen'] / res['coalGCV']),
		'LossDueToH2OInFuel' : (res['coalMoist'] * (584 + 0.45 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp'])) / res['coalGCV']),
		'LossDueToPartialCombustion' : res['partialCombustionLoss'],
		'LossDueToRadiation' : res['lossDueToRadiation'],
		'LossESPAshUBC' : res['coalAsh'] * 65 / 100 * res['espAshUnburntCarbon'] * 8077 / (100 * res['coalGCV']),
		'LossBottomAshUBC' : res['coalAsh'] * 35 / 100 * res['bedAshUnburntCarbon'] * 8077 / (100 * res['coalGCV']),
		'LossESPAshSensible' : res['coalAsh'] * 65 / 10000 * 0.23 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp']) * 100 / res['coalGCV'],
		'LossBottomAshSensible' : res['coalAsh'] * 35 / 10000 * 0.23 * (res['bedAshTemp'] - res['ambientAirTemp']) * 100 / res['coalGCV'],
	}
	
	result['ActualAirSupplied'] = (1 + result['ExcessAir'] / 100) *  result['TheoAirRequired']
	# 0.016 * 9.1 * 0.45 * 2   ((160 - 30) * 100) = 13000) / 6000
	result['LossDueToH2OInAir'] = res['airHumidityFactor'] * result['ActualAirSupplied'] * 0.45 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp']) * 100 / res['coalGCV']
	result["massofDryFlueGas"] = result['ActualAirSupplied'] + 1 - ((res["coalMoist"] + res["coalAsh"] + res["hydrogen"]) / 100)
	result["LossDueToDryFlueGas"] =  result['massofDryFlueGas'] * 0.24 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp']) * 100 / res['coalGCV']
	result['LossTotalUBC'] = result['LossESPAshUBC'] + result['LossBottomAshUBC']
	result['LossTotalSensible'] = result['LossESPAshSensible'] + result['LossBottomAshSensible']

	result['LossTotal'] = result["LossDueToDryFlueGas"] + result["LossDueToH2OInFuel"] + result["LossDueToH2InFuel"] + result["LossDueToH2OInAir"] + result["LossTotalUBC"] + result["LossTotalSensible"] + result["LossDueToPartialCombustion"] + result["LossDueToRadiation"]
	result['boilerEfficiency'] = 100 - result['LossTotal']
	return result
		

def boilerEfficiencyType6(res):
	# result = boilerEfficiencyType3(res)
	# result["ambientAirTemp"] = ((res["paFlow"] * res["paOLTemp"]) + (res["fdFlow"] * res["fdOLTemp"])) / (res["paFlow"] + res["fdFlow"])
	# result["LossESPAshUBC"] = res["coalAsh"] * 65 / 100 * res["flyAshUnburntCarbon"] * 8077 / (100 * res["coalGCV"])
	# result["LossBottomAshUBC"] = res["coalAsh"] * 5 / 100 * res["bedAshUnburntCarbon"] * 8077 / (100 * res["coalGCV"])
	result = {}
	result["TheoAirRequired"] = 0.116 * res["carbon"] + 0.348 * res["hydrogen"] + 0.0435 * res["coalSulphur"] - 0.0435 * res["oxygen"]
	result["ExcessAir"] = (res["aphFlueGasOutletO2"] * 100) / (21 - res["aphFlueGasOutletO2"])
	result["LossDueToH2OInFuel"] = res["coalMoist"] * (584 + 0.45 * (res["aphFlueGasOutletTemp"] - res["ambientAirTemp"])) / res["coalGCV"]
	result["LossDueToH2InFuel"] = 8.937 * (584 + 0.45 * (res["aphFlueGasOutletTemp"] - res["ambientAirTemp"])) * res["hydrogen"] / res["coalGCV"]
	result["LossBedAshUBC"] =  res["coalAsh"] * 10 / 100 * res["bedAshUnburntCarbon"] * 8080 / (100 * res["coalGCV"])
	result["LossFlyAshUBC"] =  res["coalAsh"] * 90 / 100 * res["flyAshUnburntCarbon"] * 8080 / (100 * res["coalGCV"])
	result["LossDueToRadiation"] = res["LossDueToRadiation"]
	result["LossUnaccounted"] = res["LossUnaccounted"]	
	result["LossFlueGasUBC"] = res["COInFlueGasPPM"] * 28 * 5654 * 100 / ((10 ** 6) *  res["coalGCV"])
	result["ActualAirSupplied"] = (1 + result["ExcessAir"] / 100) *  result["TheoAirRequired"]
	result["LossDueToH2OInAir"] = res["airHumidityFactor"] * result["ActualAirSupplied"] * 0.45 * (res["aphFlueGasOutletTemp"] - res["ambientAirTemp"]) * 100 / res["coalGCV"]
	result["massofDryFlueGas"] = (res["carbon"] * 44 / 12 + res["coalSulphur"] * 64 / 32 + res["nitrogen"] + result["ActualAirSupplied"] * 77 + (result["ActualAirSupplied"] - result["TheoAirRequired"]) * 23) / 100
	result["LossDueToDryFlueGas"] = result["massofDryFlueGas"] * 0.24 * (res["aphFlueGasOutletTemp"] - res["ambientAirTemp"]) * 100 / res["coalGCV"]
	result["LossTotal"] =  result["LossDueToDryFlueGas"] + result["LossDueToH2OInFuel"] + result["LossDueToH2InFuel"] + result["LossDueToH2OInAir"] + result["LossBedAshUBC"] + result["LossFlyAshUBC"] +result["LossUnaccounted"] + result["LossDueToRadiation"] + result["LossFlueGasUBC"]
	result["boilerEfficiency"] = 100 - result["LossTotal"]
	result["LossDueToDryFlueGas"] =  result["massofDryFlueGas"] * 0.23 * (res["aphFlueGasOutletTemp"] - res["ambientAirTemp"]) * 100 / res["coalGCV"]
	result["LossFlyAshUBC"] = ((res["coalAsh"] / 100) * 0.9 * (res["flyAshUnburntCarbon"]) * 100) / res["coalGCV"]   
	result["LossBedAshUBC"] = ((res["coalAsh"] / 100) * 0.1 * (res["bedAshUnburntCarbon"]) * 100) / res["coalGCV"]
	result["LossDueToNonDeSuph"] = res["LossDueToNonDeSuph"]
	result["LossTotal"] = result["LossDueToDryFlueGas"] + result["LossDueToH2OInFuel"] + result["LossDueToH2InFuel"] + result["LossDueToH2OInAir"] + result["LossBedAshUBC"] + result["LossFlyAshUBC"] +result["LossUnaccounted"] + result["LossDueToRadiation"] + result["LossFlueGasUBC"] + result["LossDueToNonDeSuph"]
	result["boilerEfficiency"] = 100 - result["LossTotal"]
	return result
		

def boilerEfficiencyType7(res):
	result = boilerEfficiencyType1(res)
	result["LossDueToH2InFuel"] = 9 * (584 + 0.45 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp'])) * res['hydrogen'] / res['coalGCV']
	result['LossBedAshUBC'] = (((res["coalAsh"] / 100) * 0.20 * (res["bedAshUnburntCarbon"]) * 8080) / (100 - res["bedAshUnburntCarbon"])) * 100 / res['coalGCV']
	result['LossFlyAshUBC'] = (((res["coalAsh"] / 100) * 0.80 * (res["flyAshUnburntCarbon"]) * 8080) / (100 - res["flyAshUnburntCarbon"])) * 100 / res['coalGCV']
	result['LossSensibleBedAsh'] =  ((res["coalAsh"]  / 100) * 0.20 * 0.23) * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp']) * 100 / res['coalGCV']
	result['LossSensibleFlyAsh'] = ((res["coalAsh"]  / 100) * 0.80 * 0.23) * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp']) * 100 / res['coalGCV']
	result["LossFlueGasUBC"] = (res['COInFlueGasPPM'] * (10 ** (-4)) * res['carbon'] * 5654) / ((res['COInFlueGasPPM'] * (10 ** (-4)) + 2) * res['coalGCV']) # 2 here is co2%, make an entry in data entry page for this.
	#print "result['LossBedAshUBC']", result['LossBedAshUBC']
	#print "result['LossFlyAshUBC']", result['LossFlyAshUBC']
	#print "result['LossSensibleBedAsh']", result['LossSensibleBedAsh']
	#print "result['LossSensibleFlyAsh']", result['LossSensibleFlyAsh']
	#print "result["LossFlueGasUBC"]", result["LossFlueGasUBC"]
	if "COInFlueGasPPM" and "CO2InFlueGas" in res:
		result['LossDueToCO2'] = ((res['COInFlueGasPPM']/10000)*res['carbon']*5654)/((res['CO2InFlueGas']+(res['COInFlueGasPPM']/10000))*res['coalGCV'])
	
		
		result['LossTotal'] =  result['LossDueToDryFlueGas'] + result['LossDueToH2OInFuel'] + result['LossDueToH2InFuel'] + result['LossDueToH2OInAir'] + result['LossBedAshUBC'] + result['LossFlyAshUBC'] +result['LossSensibleBedAsh'] +result['LossSensibleFlyAsh'] +result['LossUnaccounted'] + result['LossDueToRadiation'] +result['LossDueToCO2']
	else :
		result['LossTotal'] =  result['LossDueToDryFlueGas'] + result['LossDueToH2OInFuel'] + result['LossDueToH2InFuel'] + result['LossDueToH2OInAir'] + result['LossBedAshUBC'] + result['LossFlyAshUBC'] +result['LossSensibleBedAsh'] +result['LossSensibleFlyAsh'] +result['LossUnaccounted'] + result['LossDueToRadiation'] + result["LossFlueGasUBC"]
	
	result['boilerEfficiency'] = 100 - result['LossTotal']
	# print result
	return result


def boilerEfficiencyType8(res):
	result = boilerEfficiencyType1(res)
	result["LossDueToH2InFuel"] = 9 * (584 + 0.45 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp'])) * res['hydrogen'] / res['coalGCV']
	result["LossFlyAshUBC"] = ((res["flyAshUnburntCarbon"] / (100 - res["flyAshUnburntCarbon"])) * res["coalAsh"] * 0.85 * 8080) / res['coalGCV']
	result["LossFlueGasUBC"] = (res['COInFlueGasPPM'] * (10 ** (-4)) * res['carbon'] * 5654) / ((res['COInFlueGasPPM'] * (10 ** (-4)) + 2) * res['coalGCV']) # 2 here is co2%, make an entry in data entry page for this.
	result['LossTotal'] =  result['LossDueToDryFlueGas'] + result['LossDueToH2OInFuel'] + result['LossDueToH2InFuel'] + result['LossDueToH2OInAir'] + result['LossBedAshUBC'] + result['LossFlyAshUBC'] +result['LossSensibleBedAsh'] +result['LossSensibleFlyAsh'] +result['LossUnaccounted'] + result['LossDueToRadiation'] + result["LossFlueGasUBC"]
	result['boilerEfficiency'] = 100 - result['LossTotal']
	return result


def boilerEfficiencyType9(res):
	result = boilerEfficiencyType1(res)    
	result["LossFlyAshUBC"] = ((res["coalAsh"] * (80 * res["flyAshUnburntCarbon"]) / 100) / (100 - ((80 * res["flyAshUnburntCarbon"])/100)) * 8056) / res["coalGCV"]
	result["LossBedAshUBC"] = ((res["coalAsh"] * (20 * res["bedAshUnburntCarbon"]) / 100) / (100 - ((20 * res["bedAshUnburntCarbon"])/100)) * 8056) / res["coalGCV"]
	result['LossTotal'] =  result['LossDueToDryFlueGas'] + result['LossDueToH2OInFuel'] + result['LossDueToH2InFuel'] + result['LossDueToH2OInAir'] + result['LossBedAshUBC'] + result['LossFlyAshUBC'] +result['LossSensibleBedAsh'] +result['LossSensibleFlyAsh'] +result['LossUnaccounted'] + result['LossDueToRadiation']
	result['boilerEfficiency'] = 100 - result['LossTotal']
	return result


def boilerEfficiencyType10(res):
	result = boilerEfficiencyType1(res)
	result['LossDueToDryFlueGas'] = result['massofDryFlueGas'] * 0.24 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp']) * 100 / res['coalGCV']
	result["LossDueToH2InFuel"] = 9 * (584 + 0.45 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp'])) * res['hydrogen'] / res['coalGCV']
	result["LossBedAshUBC"] = (0.2 * res["bedAshUnburntCarbon"]) / (100 - res["bedAshUnburntCarbon"]) * 8080 * res["coalAsh"] / res['coalGCV']
	result["LossFlyAshUBC"] = ((res["flyAshUnburntCarbon"] / (100 - res["flyAshUnburntCarbon"])) * res["coalAsh"] * 0.8 * 8080) / res['coalGCV']
	#result["LossFlueGasUBC"] = (res['COInFlueGasPPM'] * (10 ** (-4)) * res['carbon'] * 5654)/(((res['COInFlueGasPPM'] * (10 ** (-4))) + res['CO2InFlueGas']) * res['coalGCV'])
	result["LossSensibleBedAsh"] = (res["coalAsh"] * (20/10000))*0.23*(res['bedAshTemp'] - res['ambientAirTemp'])*100 / res['coalGCV']
	result["LossSensibleFlyAsh"] = (res["coalAsh"] * (80/10000)) * 0.23 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp']) * 100 / res['coalGCV']
	result['LossTotal'] =  result['LossDueToDryFlueGas'] + result['LossDueToH2OInFuel'] + result['LossDueToH2InFuel'] + result['LossDueToH2OInAir'] + result['LossBedAshUBC'] + result['LossFlyAshUBC'] +result['LossSensibleBedAsh'] +result['LossSensibleFlyAsh'] +result['LossUnaccounted'] + result['LossDueToRadiation']
	result['boilerEfficiency'] = 100 - result['LossTotal']
	return result

def boilerEfficiencyType11(res):
	result = {}

	result["TheoAirRequired"] = 0.116 * res["carbon"] + 0.348 * res["hydrogen"] + 0.0435 * res["coalSulphur"] - 0.0435 * res["oxygen"]
	result["ExcessAir"] = res["aphFlueGasOutletO2"] * 100 / (21 - res["aphFlueGasOutletO2"])
	result["ActualAirSupplied"] = (1 + result["ExcessAir"] / 100) * result["TheoAirRequired"]
	result["LossDueToH2OInFuel"] = res["coalMoist"] * (584 + 0.45 * (res["aphFlueGasOutletTemp"] - res["ambientAirTemp"])) / res["coalGCV"]
	result["LossDueToH2InFuel"] = 8.937 * (584 + 0.45 * (res["aphFlueGasOutletTemp"] - res["ambientAirTemp"])) * res["hydrogen"] / res["coalGCV"]
	result["LossBedAshUBC"] = ((res["coalAsh"] / 100) * 0.15 * res["bedAshUnburntCarbon"] * 8080) / (100 - res["bedAshUnburntCarbon"]) * 100 / res["coalGCV"]
	result["LossFlyAshUBC"] = ((res["coalAsh"] / 100) * 0.85 * res["flyAshUnburntCarbon"] * 8080) / (100 - res["flyAshUnburntCarbon"]) * 100 / res["coalGCV"]
	result["LossSensibleBedAsh"] = (res["coalAsh"] / 100) * 0.15 * 0.22 * (res["bedAshTemp"] - res["ambientAirTemp"]) * 100 / res["coalGCV"]
	result["LossSensibleFlyAsh"] = (res["coalAsh"] / 100) * 0.85 * 0.22 * (res["aphFlueGasOutletTemp"] - res["ambientAirTemp"]) * 100 / res["coalGCV"]
	result["LossDueToRadiation"] = res["LossDueToRadiation"]
	result["LossUnaccounted"] = res["LossUnaccounted"]
	result["LossDueToCO2"] = ((res["COInFlueGasPPM"] / 10000) * res["carbon"] * 5654) / ((res["Co2"] + (res["COInFlueGasPPM"] / 10000)) * res["coalGCV"])
	result["massofDryFlueGas"] = (res["carbon"] * 44 / 12 + res["coalSulphur"] * 64 / 32 + res["nitrogen"] + result["ActualAirSupplied"] * 77 + (result["ActualAirSupplied"] - result["TheoAirRequired"]) * 23) / 100
	result["LossDueToDryFlueGas"] = result["massofDryFlueGas"] * 0.23 * (res["aphFlueGasOutletTemp"] - res["ambientAirTemp"]) * 100 / res["coalGCV"]
	result["LossDueToH2OInAir"] = res["airHumidityFactor"] * result["ActualAirSupplied"] * 0.45 * (res["aphFlueGasOutletTemp"] - res["ambientAirTemp"]) * 100 / res["coalGCV"]
	result["LossTotal"] = result["LossDueToDryFlueGas"] + result["LossDueToH2OInFuel"] + result["LossDueToH2InFuel"] + result["LossDueToH2OInAir"] + result["LossBedAshUBC"] + result["LossFlyAshUBC"] + result["LossSensibleBedAsh"] + result["LossSensibleFlyAsh"] + result["LossUnaccounted"] + result["LossDueToRadiation"] + result["LossDueToCO2"]
	result["boilerEfficiency"] = 100 - result["LossTotal"]

	return result

# def boilerEfficiencyType11(res):
# 	# print "***********RES*************"
#    # print json.dumps(res, indent=4)
# 	# print "***", "flyAshUnburntCarbon" in res
# 	# print " **", "bedAshUnburntCarbon" in res
# 	for i in ["carbon", "hydrogen", "coalSulphur", "oxygen", "aphFlueGasOutletO2", "coalMoist", "aphFlueGasOutletTemp", "ambientAirTemp", "coalGCV","coalAsh","airHumidityFactor", "LossUnaccounted", "LossDueToRadiation", "flyAshUnburntCarbon", "bedAshUnburntCarbon","COInFlueGasPPM","Co2"]:
# 		if i not in res:
# 			# print "this is missing********: ", str(i)
# 			return json.dumps({"error" : str(i) + " missing"}), 400
	
# 	result = {
# 		'TheoAirRequired' : 0.116 * res['carbon'] + 0.348 * res['hydrogen'] + 0.0435 * res['coalSulphur'] - 0.0435 * res['oxygen'],
# 		'ExcessAir' : (res['aphFlueGasOutletO2'] * 100) / (21 - res['aphFlueGasOutletO2']),
# 		'LossDueToH2OInFuel' : res['coalMoist'] * (584 + 0.45 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp'])) / res['coalGCV'],
# 		'LossDueToH2InFuel' : 8.937 * (584 + 0.45 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp'])) * res['hydrogen'] / res['coalGCV'],
		
# 		'LossBedAshUBC' : (((res["coalAsh"] / 100) * 0.15 * (res["bedAshUnburntCarbon"]) * 8080) / (100 - res["bedAshUnburntCarbon"])) * 100 / res['coalGCV'],
# 		'LossFlyAshUBC' : (((res["coalAsh"] / 100) * 0.85 * (res["flyAshUnburntCarbon"]) * 8080) / (100 - res["flyAshUnburntCarbon"])) * 100 / res['coalGCV'],
# 		'LossSensibleBedAsh' :  ((res["coalAsh"]  / 100) * 0.15 * 0.22) * (res['bedAshTemp'] - res['ambientAirTemp']) * 100 / res['coalGCV'],
# 		'LossSensibleFlyAsh' : ((res["coalAsh"]  / 100) * 0.85 * 0.22) * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp']) * 100 / res['coalGCV'],
# 		'LossDueToRadiation' : res['LossDueToRadiation'],
# 		'LossUnaccounted' : res['LossUnaccounted'],
# 		'LossDueToCO2' : ((res['COInFlueGasPPM']/10000)*res['carbon']*5654)/((res['Co2']+(res['COInFlueGasPPM']/10000))*res['coalGCV'])
# 	}
# 	# print "LossSensibleBedAsh:::::::::::::::::"
# 	# print result["LossSensibleBedAsh"]
# 	result['ActualAirSupplied'] = (1 + result['ExcessAir'] / 100) *  result['TheoAirRequired']
# 	# print "loss cal: ", res['airHumidityFactor'], result['ActualAirSupplied'], res['aphFlueGasOutletTemp'], res['ambientAirTemp']
# 	result['LossDueToH2OInAir'] = res['airHumidityFactor'] * result['ActualAirSupplied'] * 0.45 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp']) * 100 / res['coalGCV']
	
# 	result['massofDryFlueGas'] = (res['carbon'] * 44 / 12 + res['coalSulphur'] * 64 / 32 + res['nitrogen'] + result['ActualAirSupplied'] * 77 + (result['ActualAirSupplied'] - result['TheoAirRequired']) * 23) / 100
# 	result['LossDueToDryFlueGas'] = result['massofDryFlueGas'] * 0.23 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp']) * 100 / res['coalGCV']
# 	# print result['massofDryFlueGas'], (res['aphFlueGasOutletTemp'] - res['ambientAirTemp']) * 100, res['coalGCV']
# 	result['LossTotal'] =  result['LossDueToDryFlueGas'] + result['LossDueToH2OInFuel'] + result['LossDueToH2InFuel'] + result['LossDueToH2OInAir'] + result['LossBedAshUBC'] + result['LossFlyAshUBC'] +result['LossSensibleBedAsh'] +result['LossSensibleFlyAsh'] +result['LossUnaccounted'] + result['LossDueToRadiation'] + result['LossDueToCO2']
# 	result['boilerEfficiency'] = 100 - result['LossTotal']
# 	# print "result of boilereff"
# 	# print result['boilerEfficiency']

# 	return result
	'''
	if result['boilerEfficiency'] < 95:
		return result
	else:
		return json.dumps({"error" : "Boiler efficiency is above 95" + str(result['boilerEfficiency'])}), 400


	'''

def boilerEfficiencyType12(res):
	result = {}
	# print json.dumps(res, indent=4)
	#print "In efficiency: ", res["coalGCV"], res["coalAsh"], res["aphFlueGasOutletTemp"], res["ambientAirTemp"]
	#Weighted_Air_I_L_temp_APH=(PA_FLOW * Air_I_L_temp_PA_outlet_DEG_C + FD_FLOW * Air_I_L_temp_FD_outlet_DEG_C) / (PA_FLOW + FD_FLOW)
	result["ambientAirTemp"] = ((res["paFlow"] * res["paOLTemp"]) + (res["fdFlow"] * res["fdOLTemp"])) / (res["paFlow"] + res["fdFlow"])
	result["LossESPAshUBC"] = res["coalAsh"] * 65 / 100 * res["flyAshUnburntCarbon"] * 8077 / (100 * res["coalGCV"])
	result["LossBottomAshUBC"] = res["coalAsh"] * 5 / 100 * res["bedAshUnburntCarbon"] * 8077 / (100 * res["coalGCV"])
	result["LossESPAshSensible"] = res["coalAsh"] * 65 / 10000 * 0.23 * (res["aphFlueGasOutletTemp"] - res["ambientAirTemp"]) * 100 / res["coalGCV"]
	result["LossBottomAshSensible"] = res["coalAsh"] * 5 / 10000 * 0.23 * (res["bedAshUnburntCarbon"] - res["ambientAirTemp"]) * 100 / res["coalGCV"]
	result["LossDueToH2InFuel"] = 8.937 * (584 + 0.45 * (res["aphFlueGasOutletTemp"] - res["ambientAirTemp"])) * res["hydrogen"] / res["coalGCV"]
	result["LossDueToH2OInFuel"] = res["coalMoist"] * (584 + 0.45 * (res["aphFlueGasOutletTemp"] - res["ambientAirTemp"])) / res["coalGCV"]
	result["LossDueToRadiation"] = res["LossDueToRadiation"]
	result["LossDueToPartialCombustion"] = res["partialCombustionLoss"]
	result["Other_Losses_Plant_Specific_prc"] = res["Other_Losses_Plant_Specific_prc"]
	result["TheoAirRequired"] = 0.116 * res["carbon"] + 0.348 * res["hydrogen"] + 0.0435 * res["coalSulphur"] - 0.0435 * res["oxygen"]
	result["ExcessAir"] = res["aphFlueGasOutletO2"] * 100 / (21 - res["aphFlueGasOutletO2"])
	result["ActualAirSupplied"] = (1 + result["ExcessAir"] / 100) * result["TheoAirRequired"]
	result["massofDryFlueGas"] = (res["carbon"] * 44 / 12 + res["coalSulphur"] * 64 / 32 + res["nitrogen"] + result["ActualAirSupplied"] * 77 + (result["ActualAirSupplied"] - result["TheoAirRequired"]) * 23) / 100
	result["LossDueToH2OInAir"] = res["airHumidityFactor"] * result["ActualAirSupplied"] * 0.45 * (res["aphFlueGasOutletTemp"] - res["ambientAirTemp"]) * 100 / res["coalGCV"]
	result["LossDueToDryFlueGas"] = result["massofDryFlueGas"] * 0.24 * (res["aphFlueGasOutletTemp"] - res["ambientAirTemp"]) * 100 / res["coalGCV"]
	result["LossTotalUBC"] = result["LossESPAshUBC"] + result["LossBottomAshUBC"] 
	result["LossTotalSensible"] = result["LossESPAshSensible"] + result["LossBottomAshSensible"] 
	result["LossTotal"] = result["LossTotalUBC"] + result["LossTotalSensible"] + result["LossDueToDryFlueGas"] + result["LossDueToH2OInFuel"] + result["LossDueToH2InFuel"] + result["LossDueToH2OInAir"] + result["LossDueToPartialCombustion"] + result["Other_Losses_Plant_Specific_prc"]
	result["boilerEfficiency"] = 100 - result["LossTotal"]
	return result 


def boilerEfficiencyType13(res):
	result = {}
	result["barometricPressurePSI"] = (res["barometricPressInMbar"] * 14.5038 / 1000.0)
	result["dryBulbTempAtFDInlet"] =  (res["saInletTempAtAph"] - 3.0)
	result["dryBulbTempAtFDInletInFarenheit"] =  ((result["dryBulbTempAtFDInlet"] * 1.8) + 32.0)
	result["saturationPressureOfWaterVaporAtDbtInPSI"] = (0.019257 + (1.289016 * (10**(-3)) * result["dryBulbTempAtFDInletInFarenheit"]) + (1.21122*(10**(-5))*(result["dryBulbTempAtFDInletInFarenheit"]**2)) + (4.534007*(10**(-7))*(result["dryBulbTempAtFDInletInFarenheit"]**3)) + (6.84188*(10**(-11))*(result["dryBulbTempAtFDInletInFarenheit"]**4)) + (2.197092*(10**(-11))*(result["dryBulbTempAtFDInletInFarenheit"]**5)))
	result["saturationPressureOfWaterVaporAtDbtInBar"] =  result["saturationPressureOfWaterVaporAtDbtInPSI"] / 14.5038
	result["partialPressureOfWaterVaporInAirPsi"] = result["saturationPressureOfWaterVaporAtDbtInPSI"] * 0.01 * res["relativeHumidity"]
	result["partialPressureOfWaterVaporInAirMbar"] = result["partialPressureOfWaterVaporInAirPsi"] / 14.5038
	result["moistureInAirPerKgOfDryAir"] = 0.622 * (result["partialPressureOfWaterVaporInAirPsi"] / (result["barometricPressurePSI"] - result["partialPressureOfWaterVaporInAirPsi"]))
	result["airHumidityFactor"] = round(result["moistureInAirPerKgOfDryAir"],3)
	result["TheoAirRequired"] = (11.6*res["carbon"]/100)+34.8*(res["hydrogen"]-res["oxygen"]/8)/100+(4.35*res["coalSulphur"]/100)
	result["averageO2_dryBasis"] = res["aphFlueGasOutletO2"] + 0.5
	result["averageO2AtAphOutlet"] = ((20.9 * res["LeakageacrossAPH"]) + (90.0 * result["averageO2_dryBasis"])) / (90.0 + res["LeakageacrossAPH"]) 
	result["ExcessAir"] = (result["averageO2AtAphOutlet"] * 100) / (21 - result["averageO2AtAphOutlet"])
	result["ActualAirSupplied"] = (1 + result["ExcessAir"] / 100) *  result["TheoAirRequired"]
	result["massofDryFlueGas"] = (res["carbon"] * 44 / 12 + res["coalSulphur"] * 64 / 32 + res["nitrogen"] + result["ActualAirSupplied"] * 77 + (result["ActualAirSupplied"] - result["TheoAirRequired"]) * 23) / 100
	result["weightedAirInletTempToAph"] = ((res["paFlow"] * res["paInletTempAtAph"]) + (res["fdFlow"] * res["saInletTempAtAph"])) / (res["paFlow"] + res["fdFlow"])
	result["LossDueToDryFlueGas"] = result["massofDryFlueGas"] * 0.24 * (res["aphFlueGasOutletTemp"] - result["weightedAirInletTempToAph"]) * 100 / res["coalGCV"]
	result["LossDueToH2OInFuel"] = res["coalMoist"] * (584 + (0.45 * (res["aphFlueGasOutletTemp"] - result["weightedAirInletTempToAph"]))) / res["coalGCV"]
	result["LossDueToH2InFuel"] = 8.937 * (584 + 0.45 * (res["aphFlueGasOutletTemp"] - result["weightedAirInletTempToAph"])) * res["hydrogen"] / res["coalGCV"]
	result["LossDueToH2OInAir"] = result["airHumidityFactor"] * result["ActualAirSupplied"] * 0.45*(res["aphFlueGasOutletTemp"] - result["weightedAirInletTempToAph"]) * 100 / res["coalGCV"]
	result["co2AtAphOutlet"] = 19.4 - res["aphFlueGasOutletO2"]
	result["coAtAphOutletMeasuredPpm"] = res["coDilutionAcrossEspTest"] + res["CO_Online_ESP_O_L"]
	result["coAtAphOutletInPercentage"] = result["coAtAphOutletMeasuredPpm"] * 100 / 10**6
	result["LossDueToPartialCombustion"] = round((result["coAtAphOutletInPercentage"] * res["carbon"] / 100.0) / (result["coAtAphOutletInPercentage"] + result["co2AtAphOutlet"]) * 5744 * 100 / res["coalGCV"], 3)
	result["LossESPAshUBC"] = (res["flyAshRatioInPercent"] / 100) * res["coalAsh"] * res["flyAshUnburntCarbon"] * 8077 / (100 * res["coalGCV"])
	result["LossBottomAshUBC"] =  (res["bottomAshRatioInPercent"] / 100) * res["coalAsh"] * res["bedAshUnburntCarbon"] * 8077 / (100 * res["coalGCV"])
	result["LossESPAshSensible"] =  0.01 * res["flyAshRatioInPercent"] * res["coalAsh"] * 0.01 * (0.16 * (1.8 * res["aphFlueGasOutletTemp"] + 32)+ 1.09 * (10**(-4)) * ((1.8 * res["aphFlueGasOutletTemp"] +32)**2)  - 2.843 * (10**(-8)) * ((1.8 * res["aphFlueGasOutletTemp"] + 32)**3) - 12.95) * 2.326 / 4.1868 * 100 / res["coalGCV"]
	result["LossBottomAshSensible"] = 0.01 * res["bottomAshRatioInPercent"]  * res["coalAsh"]  * 0.01 * (0.16 * (1.8 * res["bottomAshTempConstant"]+ 32) + 1.09 * (10**(-4)) * ((1.8 * res["bottomAshTempConstant"] +32)**2) - 2.843 * (10**(-8)) * ((1.8 * res["bottomAshTempConstant"] + 32)**3) - 12.95) * 2.326 / 4.1868 * 100  /  res["coalGCV"] + 31500 * 3.6 * 17.54 / (1000 * res["coalFlow"])  / res["coalGCV"] / 4.1868 * 100
	result["LossTotalUBC"] = result["LossESPAshUBC"] + result["LossBottomAshUBC"]
	result["LossTotalSensible"] = result["LossESPAshSensible"] + result["LossBottomAshSensible"]
	result["LossDueToRadiation"] = res["LossDueToRadiation"]
	result["LossTotal"] = result["LossDueToDryFlueGas"] + result["LossDueToH2OInFuel"] + result["LossDueToH2InFuel"] + result["LossDueToH2OInAir"] + result["LossDueToPartialCombustion"] + result["LossTotalUBC"] + result["LossTotalSensible"] + result["LossDueToRadiation"]
	result["boilerEfficiencyAsPerAsmePtc4"] = 100.0 - result["LossTotal"]
	result["LossMillRejects"] = (res["millRejectsCV"] * res["millRejectsQuantity"] * 100.0) / (res["load"] * 0.7 * 1000.0 * res["coalGCV"])
	result["LossBlowDownLeakage"] = (0.8 * res["dmMakeUpWater"] * 300 + 0.2 * res["dmMakeUpWater"] * 150) * 100 / (res["load"] * 0.7 * res["coalGCV"])
	result["LossPlantSpecificOther"] = res["plantSpecificOtherLosses"]
	result["boilerEfficiency"] = result["boilerEfficiencyAsPerAsmePtc4"] - result["LossMillRejects"] - result["LossBlowDownLeakage"] - result["LossPlantSpecificOther"]
	return result

def boilerEfficiencyType14(res):
	# print (("TYPE 14 14 ") * 14 )
	# print json.dumps(res, indent=4)
	result = {}
	#Pws = 0.61078 * exp[(17.27 * T)/(T + 237.3)]
	#where T is the temperature in Celsius.
	result["saturationVaporPressure"] = 0.61078 * math.exp(((17.27 * res["ambientAirTemp"]) / (res["ambientAirTemp"] + 237.3)))

	#Pw = RH * Pws/100
	#where RH is the relative humidity in percent.
	result["vaporPressure"] = res["ambientRelativeHumidityPRC"]  * result["saturationVaporPressure"]

	#W = 0.622 * Pw / (P - Pw)
	#where P is the atmospheric pressure in kPa (usually taken as 101.325 kPa at sea level).
	result["specificHumidity"] = 0.622 * result["vaporPressure"]  / ((res["ambientAirPressurePascal"]*100 )- 0.378 * result["vaporPressure"])

	result["moistureContentInAir"] = result["specificHumidity"] / (1.0 - result["specificHumidity"])

	#(('APH A O/L O2'-'APH A I/L O2')/(21-'APH A O/L O2'))*100
	result["aphLeakagePassA"] = 100.0 * (res["aphFlueGasOutletO2_A"] - res["aphFlueGasInletO2_A"]) / (21.0 - res["aphFlueGasOutletO2_A"]) 
	result["aphLeakagePassB"] = 100.0 * (res["aphFlueGasOutletO2_B"] - res["aphFlueGasInletO2_A"]) / (21.0 - res["aphFlueGasOutletO2_B"]) 

	#((APH Leakage Pass-A + APH Leakage Pass-B)/2*0.01*(APH O/L FG Temp -APH I/L FG Temp))+APH O/L FG Temp
	result["flueGasTempForNOAphLeakage"] = (((result["aphLeakagePassA"] + result["aphLeakagePassB"]) / 2) * 0.01 * (res["aphFlueGasOutletTemp"] - res["aphFlueGasInletTemp"])) + res["aphFlueGasOutletTemp"]

	#Ratio of SA to Total Air * APH SA I/L Temp. + Ratio of PA to Total Air * APH PA I/L Temp
	result["weightedAphInletTemp"] = res["ambientAirTemp"]

	result["avgO2AtAphOutlet"] = (res["aphFlueGasOutletO2_A"] + res["aphFlueGasOutletO2_B"]) / 2.0 #correct formula but now B pass is showing incorrect value hence using only A values --- check in future
	result["avgO2AtAphOutlet"] = res["aphFlueGasOutletO2_A"] 

	result["excessAirSupplied"] = result["avgO2AtAphOutlet"] / (21 - result["avgO2AtAphOutlet"]) * 100.0

	result["theoriticalAirRequired"] = ((11.6*res["carbon"]) + (34.8 * (res["hydrogen"]) - (res["oxygen"] / 8.0)) + (4.35 * res["coalSulphur"])) / 100.0

	result["actualMassOfAirSupplied"] = result["theoriticalAirRequired"] * (1 + (result["excessAirSupplied"] / 100.0))

	result["massOfDryFlueGas"] = (((res["carbon"] / 100.0) * 44.0) / 12.0) + (res["nitrogen"] / 100.0) + (result["actualMassOfAirSupplied"] * 77.0 / 100.0) + (((result["actualMassOfAirSupplied"] - result["theoriticalAirRequired"]) * 23.0) / 100.0)

	result["totalUnburntCarbonInAsh"] = (res["coalAsh"] * res["bedAshUnburntCarbon"] * 10 * 0.01 * 0.01 * 0.01) + (res["coalAsh"] * res["flyAshUnburntCarbon"] * 90 * 0.01 * 0.01 * 0.01)

	result["carbonInAsh"] = (res["flyAshUnburntCarbon"] * 90 * 0.01) + (res["bedAshUnburntCarbon"] * 10 * 0.01)

	result["carbonInAshPerKgOfFuel"] = ((res["coalAsh"] / 100.0) * result["carbonInAsh"]) / (100.0 - result["carbonInAsh"])

	result["empiricalCO2"] = 18.68 - result["avgO2AtAphOutlet"]

	result["weightOfDryFlueGas"] = (res["carbon"] + (res["coalSulphur"] / 2.67) - 100 * result["carbonInAshPerKgOfFuel"]) / (12 * result["empiricalCO2"])

	result["sensibleHeatOfDryGas"] = result["weightOfDryFlueGas"] * 30.6 * (res["aphFlueGasOutletTemp"] - result["weightedAphInletTemp"])
	
	result["LossDueToDryFlueGas"] = (result["sensibleHeatOfDryGas"] * 100.0) / (res["coalGCV"] * 4.18674)

	result["sensibleHeatOfWater"] = 1.88 * (res["aphFlueGasOutletTemp"] - 25.0) + 2442 + (4.2 * (25 - result["weightedAphInletTemp"]))

	result["LossDueToH2InFuel"] = (result["sensibleHeatOfWater"] * res["hydrogen"] * 9.0) / (res["coalGCV"] * 4.18674)

	result["LossDueToH2OInFuel"] = (result["sensibleHeatOfWater"] * res["coalMoist"]) / (res["coalGCV"] * 4.18674)

	result["LossDueToH2OInAir"] =  (result["actualMassOfAirSupplied"] * result["moistureContentInAir"] * (0.45 *(res["aphFlueGasOutletTemp"] - result["weightedAphInletTemp"]) * 100.0)) / res["coalGCV"]

	result["LossDueToPartialCombustion"] = 0.0 # no tag present for JSW for CO, hence 

	result["LossDueToUnburntCarbon"] = result["totalUnburntCarbonInAsh"] * 8084.0 * 100.0 / res["coalGCV"]

	result["LossDueToRadiation"] = 0.99

	result["LossTotal"] = result["LossDueToDryFlueGas"] + result["LossDueToH2InFuel"] + result["LossDueToH2OInFuel"] + result["LossDueToH2OInAir"] + result["LossDueToPartialCombustion"] + result["LossDueToUnburntCarbon"] + result["LossDueToRadiation"]

	result["boilerEfficiency"] = 100.0 - result["LossTotal"]

	# print result["boilerEfficiency"]
	return result

def boilerEfficiencyType15(res):
	# print json.dumps(res, indent=4)
	# print "***", "flyAshUnburntCarbon" in res
	# print " **", "bedAshUnburntCarbon" in res
	for i in ["carbon", "hydrogen", "coalSulphur", "oxygen", "aphFlueGasOutletO2", "coalMoist", "aphFlueGasOutletTemp", "ambientAirTemp", "coalGCV","coalAsh","airHumidityFactor", "LossUnaccounted", "LossDueToRadiation", "flyAshUnburntCarbon", "bedAshUnburntCarbon"]:
		if i not in res:
			return json.dumps({"error" : str(i) + " missing"}), 400
	
	
	result = {
		'TheoAirRequired' : 0.116 * res['carbon'] + 0.348 * res['hydrogen'] + 0.0435 * res['coalSulphur'] - 0.0435 * res['oxygen'],
		'ExcessAir' : (res['aphFlueGasOutletO2'] * 100) / (21 - res['aphFlueGasOutletO2']),
		'LossDueToH2OInFuel' : res['coalMoist'] * (584 + 0.45 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp'])) / res['coalGCV'],
		'LossDueToH2InFuel' :9* (584 + 0.45 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp'])) * res['hydrogen'] / res['coalGCV'],

		
		'LossBedAshUBC' :  res['coalAsh'] * 20 / 100 * res['bedAshUnburntCarbon'] * 8080 / (100 * res['coalGCV']),
		'LossFlyAshUBC' :  res['coalAsh'] * 80 / 100 * res['flyAshUnburntCarbon'] * 8080 / (100 * res['coalGCV']),
		
		'LossDueToRadiation' : res['LossDueToRadiation'],
		'LossUnaccounted' : res['LossUnaccounted'],
	}
	# print "$$$$$$$$$$$$$$$$$$$ Values here: ", res['coalAsh'], res['flyAshUnburntCarbon'], res['coalGCV'], result['LossFlyAshUBC']
	
	result['LossFlueGasUBC'] = res['COInFlueGasPPM'] * 28 * 5654 * 100 / ((10 ** 6) *  res['coalGCV'])
	result['ActualAirSupplied'] = (1 + result['ExcessAir'] / 100) *  result['TheoAirRequired']
	# print "loss cal: ", res['airHumidityFactor'], result['ActualAirSupplied'], res['aphFlueGasOutletTemp'], res['ambientAirTemp']
	result['LossDueToH2OInAir'] = res['airHumidityFactor'] * result['ActualAirSupplied'] * 0.45 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp']) * 100 / res['coalGCV']
	result['massofDryFlueGas'] = (res['carbon'] * 44 / 12 + res['coalSulphur'] * 32 / 64 + res['ActualAirSupplied'] * 77/100 + (res['oxygen']* 32) / 100)
	# result['massofDryFlueGas'] = (res['carbon'] * 44 / 12 + res['coalSulphur'] * 64 / 32 + res['nitrogen'] + result['ActualAirSupplied'] * 77 + (result['ActualAirSupplied'] - result['TheoAirRequired']) * 23) / 100
	result['LossDueToDryFlueGas'] = result['massofDryFlueGas'] * 0.24 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp']) * 100 / res['coalGCV']
	result['LossTotal'] =  result['LossDueToDryFlueGas'] + result['LossDueToH2OInFuel'] + result['LossDueToH2InFuel'] + result['LossDueToH2OInAir'] + result['LossBedAshUBC'] + result['LossFlyAshUBC'] +result['LossUnaccounted'] + result['LossDueToRadiation'] + result['LossFlueGasUBC']
	result['boilerEfficiency'] = 100 - result['LossTotal']
	# print json.dumps(result, indent=4)
	return result

def boilerEfficiencyType16(res):
	for i in ["carbon", "hydrogen", "coalSulphur", "oxygen", "aphFlueGasOutletO2", "coalMoist", "aphFlueGasOutletTemp", "ambientAirTemp", "coalGCV", 
		"coalAsh", "airHumidityFactor", "COInFlueGasPPM", "LossUnaccounted", "LossDueToRadiation", "flyAshUnburntCarbon", "bedAshUnburntCarbon"]:
		if i not in res:
			return json.dumps({"error": f"{i} missing"}), 400
	result = {}
	Fcdc = res['coalFC'] / (1 - ((1.1 * res['coalAsh']) / 100 - res['coalMoist'] / 100))
	Vmdf = 100 - Fcdc
	Cdf = Fcdc + (0.9 * Vmdf) - 14
	Hdf = Vmdf * (7.35 / (Vmdf + 10) - 0.013)
	Ndf = 2.1 - (0.012 * Vmdf)

	result['carbon'] = (Cdf * (res['coalVM'] + res['coalFC'])) / (Vmdf + Fcdc)
	result['hydrogen'] = (Hdf * (res['coalVM'] + res['coalFC'])) / (Vmdf + Fcdc)
	result['nitrogen'] = (Ndf * (res['coalVM'] + res['coalFC'])) / (Vmdf + Fcdc)
	result['coalSulphur'] = 0.009 * (res['coalFC'] + res['coalVM'])
	result["oxygen"] = (100  - result['carbon'] - result['hydrogen'] - result['coalSulphur'] - result['nitrogen'] - res['coalAsh'] - res['coalMoist'])
	# result["TheoCO2"] = 
	result['TheoAirRequired'] = (0.1143 * result['carbon'] + 0.345 * result['hydrogen'] - 0.043125 * result['oxygen'] + 0.0432 * result['coalSulphur'])
	result['ExcessAir'] = (res['aphFlueGasOutletO2'] * 100) / (21 - res['aphFlueGasOutletO2'])
	result['ActualAirSupplied'] = (1 + result['ExcessAir'] / 100) * result['TheoAirRequired']
	result['massOfDryFlueGas'] = (((result['carbon'] / 100.0) * 44.0 / 12.0) + (result['nitrogen'] / 100.0) + (result['ActualAirSupplied'] * 77.0 / 100.0) + ((result['ActualAirSupplied'] - result['TheoAirRequired']) * 23.0 / 100.0))
	result['LossDueToDryFlueGas'] = (result['massOfDryFlueGas'] * 0.23 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp'])  / res['coalGCV']) * 100
	result['LossDueToH2InFuel'] = (9 * result['hydrogen'] * (584 + 0.23 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp']))  / res['coalGCV'])
	result['LossDueToH2OInFuel'] = (res['coalMoist'] * (584 + 0.23 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp'])) / res['coalGCV']) 
	result['LossDueToH2OInAir'] = (res['airHumidityFactor'] * result['ActualAirSupplied'] * 0.23 * (res['aphFlueGasOutletTemp'] - res['ambientAirTemp']) * 100 / res['coalGCV'])
	#result['LossFlueGasUBC'] = (res['COInFlueGasPPM'] * 28 * 5744 * 100 / ((10 ** 6) * res['coalGCV'])) # this is removed from total loass
	result["LossDueToRadiation"] = res["LossDueToRadiation"]
	result["LossUnaccounted"] = res["LossUnaccounted"]
	result["LossESPAshUBC"] = (res["coalAsh"] * 65 / 100 * res["flyAshUnburntCarbon"] * 8077 / (100 * res["coalGCV"]))
	result["LossBottomAshUBC"] = (res["coalAsh"] * 5 / 100 * res["bedAshUnburntCarbon"] * 8077 / (100 * res["coalGCV"]))
	result['LossTotal'] = (result['LossDueToDryFlueGas'] + result['LossDueToH2InFuel'] + result['LossDueToH2OInFuel'] + result['LossDueToH2OInAir'] 
		+ result['LossBottomAshUBC'] + result['LossESPAshUBC'] + result['LossUnaccounted'] + result['LossDueToRadiation'])
	result['boilerEfficiency'] = 100 - result['LossTotal']
	return result

def boilerEfficiencyType17(res):
	print("calculation of boiler efficiency in DBPOWER")
	print(res)

	result={}
	result["flyAshRatioInPercent"]=(res["flyAshUnburntCarbon"])/(res["bedAshUnburntCarbon"]+res["flyAshUnburntCarbon"])*100
	result["bottomAshRatioInPercent"]=(res["bedAshUnburntCarbon"])/(res["bedAshUnburntCarbon"]+res["flyAshUnburntCarbon"])*100
	result["TheoAirRequired"] = (11.6*res["carbon"]/100)+34.8*(res["hydrogen"]-res["oxygen"]/8)/100+(4.35*res["coalSulphur"]/100)
	result["ExcessAir"] = (res["averageO2AtAphOutlet"] * 100) / (21 - res["averageO2AtAphOutlet"])
	result["ActualAirSupplied"] = (1 + result["ExcessAir"] / 100) *  result["TheoAirRequired"]
	result["massofDryFlueGas"] = (res["carbon"] * 44 / 12 + res["coalSulphur"] * 64 / 32 + res["nitrogen"]/100 + result["ActualAirSupplied"] * 77 + (result["ActualAirSupplied"] - result["TheoAirRequired"]) * 23) / 100
	result["LossDueToDryFlueGas"] = result["massofDryFlueGas"] * 0.24 * (res["aphFlueGasOutletTemp"] - res["ambientAirTemp"]) * 100 / res["coalGCV"]
	result["LossDueToH2InFuel"] =  9 * (584 + 0.45 * (res["aphFlueGasOutletTemp"] - res["ambientAirTemp"])) * res["hydrogen"] / res["coalGCV"]
	result["LossDueToH2OInFuel"] = res["coalMoist"] * (584 + (0.45 * (res["aphFlueGasOutletTemp"] - res["ambientAirTemp"]))) / res["coalGCV"]
	result["lossDueToCO2"]= ((0*(res["carbon"]/100))/(0+0.07162))*(5744/res["coalGCV"])*100
	result["LossESPAshUBC"] = (result["flyAshRatioInPercent"] / 100) * res["coalAsh"] * res["flyAshUnburntCarbon"] * 8056 / (100 * res["coalGCV"])
	result["LossBottomAshUBC"] =  (result["bottomAshRatioInPercent"] / 100) * res["coalAsh"] * res["bedAshUnburntCarbon"] * 8056 / (100 * res["coalGCV"])
	result["LossESPAshSensible"] =(0.16*res ["coalAsh"]*result["flyAshRatioInPercent"]*(res["aphFlueGasOutletTemp"]-res['ambientAirTemp']))*100/100/100/res["coalGCV"]
	result["LossBottomAshSensible"] = (0.16*res ["coalAsh"]*result["bottomAshRatioInPercent"]*(1100-res['ambientAirTemp']))*100/100/100/res["coalGCV"]
	result["LossTotalUBC"] = result["LossESPAshUBC"] + result["LossBottomAshUBC"]
	result["LossTotalSensible"] = result["LossESPAshSensible"] + result["LossBottomAshSensible"]
	result["LossDueToRadiation"]=res["LossDueToRadiation"]
	result["LossDueToH2OInAir"]=(result["ActualAirSupplied"] *res["airHumidityFactor"]*0.45*(res["aphFlueGasOutletTemp"]-res["ambientAirTemp"])*100/(res["coalGCV"]))
	result["LossTotal"] = result["lossDueToCO2"]+result["LossDueToDryFlueGas"] + result["LossDueToH2OInFuel"] + result["LossDueToH2InFuel"] + result["LossDueToH2OInAir"]  + result["LossTotalUBC"] + result["LossTotalSensible"] + res["LossDueToRadiation"]
	result["boilerEfficiency"] = 100-result["LossTotal"]
	return result	

def boilerEfficiencyType18(res):
	result = boilerEfficiencyType1(res) 
	print("result in type18")
	# result["LossFlyAshUBC"] =(45/100)*(res["coalAsh"]/(100-18.91))*(8052*(18.91/100))/(res["coalGCV"])*100
	# result["LossBedAshUBC"] =(55/100)*(res["coalAsh"]/100)*(8052*(8.91/100))/(res["coalGCV"])*100
	res["LossFlyAshUBC"]=(45/100)*(res["coalAsh"]/(100-res["flyAshUnburntCarbon"]))*(8052*(res["flyAshUnburntCarbon"]/100))/(res["coalGCV"])*100
	res["LossBedAshUBC"]=(55/100)*(res["coalAsh"]/(100-res["bedAshUnburntCarbon"]))*(8052*(res["bedAshUnburntCarbon"]/100))/(res["coalGCV"])*100
	
	result['LossTotal'] =  result['LossDueToDryFlueGas'] + result['LossDueToH2OInFuel'] + result['LossDueToH2InFuel'] + result['LossDueToH2OInAir'] + result['LossBedAshUBC'] + result['LossFlyAshUBC'] +result['LossSensibleBedAsh'] +result['LossSensibleFlyAsh'] +result['LossUnaccounted'] + result['LossDueToRadiation']
	result['boilerEfficiency'] = 100 - result['LossTotal']
	return result




def getLastValues(taglist,end_absolute=0):
	endTime = int((time.time()*1000) + (5.5*60*60*1000))
	if end_absolute !=0:
		query = {"metrics": [],"start_absolute": 1, "end_absolute":endTime }
	else:
		query = {"metrics": [],"start_absolute":1,"end_absolute":endTime}
	for tag in taglist:
		query["metrics"].append({"name": tag,"order":"desc","limit":1})
	try:
		res = requests.post(config['api']['query'],json=query).json()
		df = pd.DataFrame([{"time":res["queries"][0]["results"][0]["values"][0][0]}])
		for tag in res["queries"]:
			try:
				if df.iloc[0,0] <  tag["results"][0]["values"][0][0]:
					df.iloc[0,0] =  tag["results"][0]["values"][0][0]
				df.loc[0,tag["results"][0]["name"]] = tag["results"][0]["values"][0][1]
			except:
				pass
	
	except Exception as e:
		#print(e)
		return pd.DataFrame()
	return df

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
		
	elif fuelConfig["fuelUltimateConfig"]["mixtureType"]=="static":
		pass
		
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
		#print "%" * 20

		if (DYN_FUEL_FLAG == 1):
			CURR_TIME = int(time.time() * 1000 // 60000 * 60000)
			LAST_KNOWN_TS = data["time"][0]
			LAST_KNOWN_TS = LAST_KNOWN_TS
			print (CURR_TIME)
			print (LAST_KNOWN_TS)
			fuelTimeDiff = CURR_TIME - LAST_KNOWN_TS
			fuelTimeDiff_mins = fuelTimeDiff//60000

			# if (fuelTimeDiff_mins >= 15):
			#     print ("Last Known Values for hourly fuel tags are more than 15 mins old")
			#     try:
			#         process = Popen(['python', os.environ['PWD'] + '/batch_calc_hourly_params_TBWES.py', str(unitId)],\
			#                         stdout = PIPE, stderr = PIPE)
			#         stdout, stderr = process.communicate()
			#         # print stdout
			#         # print stderr
			#     except Exception as e:
			#         print ("Popen Exception\n")
			#         print (e)

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


def getBoilerRealtimeData(realtime):
	tags, names = [], {}
	for i, j in realtime.items():
		tags.append(str(j[0]))
		names[str(j[0])] = str(i)
	data = getLastValues(tags)
	if (data.shape[1]!=0):
		data.rename(columns=names, inplace=True)
	return data

def getThreshold(dataTagId):
	tagmeta=config["api"]["meta"]+'/tagmeta?filter={"where":{"dataTagId":"'+str(dataTagId)+'"},"fields": "equipmentId"}'
	response = requests.get(tagmeta)
	tagBody = json.loads(response.content) 
	eqpUrl=config["api"]["meta"]+'/equipment?filter={"where":{"id":"'+tagBody[0]["equipmentId"]+'"},"fields": "value"}'
	response = requests.get(eqpUrl)
	value = json.loads(response.content)
	
#     print(value[0]["value"]) 
	
	return value[0]["value"]


@app.route('/efficiency/onDemand', methods=['POST'])
def onDemandForCombustion():
	clientBody = request.json

	if "unitsId" not in clientBody:
		return "Units Id not in the request body", 400

	if "systemInstance" not in clientBody:
		return "System Instance not in the request body", 400

	print (clientBody)  
	unitMap = mapping[clientBody["unitsId"]]
	for boiler in unitMap["boilerEfficiency"]:
		if boiler["systemInstance"] == clientBody["systemInstance"]:
			skip_flag = 0
			if len(boiler["fuelProximate"]) > 0 :

				fuelProximateData = getProximateData(boiler["fuelProximate"], boiler["loi"], boiler)
				if fuelProximateData.shape[1]==0:
					#print("Proximate data not found in db, , skipping boiler",boiler["systemInstance"])
					skip_flag = 1
				
				# fuelProximateDesignData = boiler["fuelProximateDesign"]
				fuelProximateData = fuelProximateData.to_dict(orient="records")[0]
				fuelProximateData["type"] = unitMap["type"]
				# fuelProximateDesignData["type"] = mapping["type"]
				print ("\n\n came to proximate", fuelProximateData["type"])
				if "type" not in fuelProximateData:
					#print "res inside if"
					#print json.dumps(res,indent=4)
					print (json.dumps({"error" : "line 255 ProximateToUltimate require 'type' in if condition for calculations","res":json.dumps(fuelProximateData)}))

				else:
					if fuelProximateData["type"] == "type1":
						fuelUltimateData =  proximateToUltimateType1(fuelProximateData)
					elif fuelProximateData["type"] == "type2":
						fuelUltimateData =  proximateToUltimateType2(fuelProximateData)
					elif fuelProximateData["type"] == "type3":
						fuelUltimateData =  proximateToUltimateType3(fuelProximateData)
					elif fuelProximateData["type"] == "type4":
						fuelUltimateData =  proximateToUltimateType4(fuelProximateData)
					elif fuelProximateData["type"] == "type5":
						fuelUltimateData =  proximateToUltimateType5(fuelProximateData)
					elif fuelProximateData["type"] == "type6":
						fuelUltimateData =  proximateToUltimateType6(fuelProximateData)
					elif fuelProximateData["type"] == "type7":
						fuelUltimateData =  proximateToUltimateType7(fuelProximateData)
					elif fuelProximateData["type"] == "type8":
						fuelUltimateData =  proximateToUltimateType8(fuelProximateData)
					elif fuelProximateData["type"] == "type9":
						fuelUltimateData =  proximateToUltimateType9(fuelProximateData)
					elif fuelProximateData["type"] == "type10":
						fuelUltimateData =  proximateToUltimateType10(fuelProximateData)
					elif fuelProximateData["type"] == "type11":
						fuelUltimateData =  proximateToUltimateType11(fuelProximateData)
					elif fuelProximateData["type"] == "type12":
						fuelUltimateData = proximateToUltimateType12(fuelProximateData)
					elif fuelProximateData["type"] == "type13":
						fuelUltimateData =  proximateToUltimateType13(fuelProximateData)
					elif fuelProximateData["type"] == "type15":
						fuelUltimateData =  proximateToUltimateType15(fuelProximateData)
					elif fuelProximateData["type"] == "type17":
						fuelUltimateData =  proximateToUltimateType17(fuelProximateData)
					elif fuelProximateData["type"] == "type18":
						fuelUltimateData =  proximateToUltimateType18(fuelProximateData)
					else:
						fuelUltimateData = {}


				# fuelUltimateData = requests.post(effURL+"proximatetoultimate",json=fuelProximateData)
				# if fuelUltimateData.status_code ==200:
					# fuelUltimateData = json.loads(fuelUltimateData.content)
				# fuelUltimateDesignData = requests.post(effURL+"proximatetoultimate",json=fuelProximateDesignData)
				# if fuelUltimateDesignData.status_code ==200:
					# fuelUltimateDesignData = json.loads(fuelUltimateDesignData.content)
					
			elif len(boiler["fuelUltimate"]) > 0:
				print ("\n\n came to ultimate")

				#print(boiler["fuelUltimate"])
				fuelProximateData , fuelProximateDesignData = {}, {}	
				fuelUltimateData = getUltimateData(boiler["fuelUltimate"], boiler["loi"], boiler)	
				if fuelUltimateData.shape[1]==0:	
					#print("Proximate data not found in db, , skipping boiler",boiler["systemInstance"])	
					skip_flag = 1	
				fuelUltimateData = fuelUltimateData.to_dict(orient="records")[0]	
				fuelUltimateData["type"] = unitMap["type"]	
				
			else:
				#print("Incorrect mapping, missing fuel properties, skipping boiler",boiler["systemInstance"])
				skip_flag = 1
			

			fuelData = dict(list(fuelProximateData.items()) + list(fuelUltimateData.items()))
			# fuelDesignData = dict(list(fuelProximateDesignData.items()) + list(fuelUltimateDesignData.items()))
			#print fuelDesignData
			del fuelData["time"]

			if len(boiler["realtime"]) > 0 :
				realtimeData = getBoilerRealtimeData(boiler["realtime"])
				#print "******Boiler********* ", boiler["systemInstance"], boiler["realtime"]
				if realtimeData.shape[1]==0:
					#print("realtime data not found in db, , skipping boiler",boiler["systemInstance"])
					skip_flag = 1  
				print (realtimeData)
				realtimeData = realtimeData.to_dict(orient="records")[0] 

				print("realtime data to calc boiler efficiency") 
				print (realtimeData)

				for k,v in realtimeData.items():
					if k in clientBody.keys():
						realtimeData[k] = clientBody[k]

				print ('inserting demadn values in realtimeData')
				print (realtimeData)
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

					# realtimeDesignData = requests.post(effURL+"design",json={"realtime":boiler["realtime"],"loi":boiler["loi"],"load":realtimeData["boilerSteamFlow"],"loadTag":boiler["realtime"]["boilerSteamFlow"][0],"realtimeData":realtimeData,"unitId":unitId})
					# if realtimeDesignData.status_code ==200:
						# realtimeDesignData = json.loads(realtimeDesignData.content)
					#print(realtimeData)
					#print "$" *10
					#print(realtimeDesignData)
					# realtimeBPData = requests.post(effURL+"bestachieved",json={"realtime":boiler["realtime"],"load":realtimeData["boilerSteamFlow"],"loadTag":boiler["realtime"]["boilerSteamFlow"][0],"realtimeData":realtimeData,"unitId":unitId})
					# if realtimeBPData.status_code ==200:
						# realtimeBPData = json.loads(realtimeBPData.content)
						# for i,j in realtimeBPData.items():
							# if j!=j :
								# realtimeBPData[i] = realtimeData[i]
								
					boilerInputData =  dict(list(fuelData.items()) + list(realtimeData.items()) + list(boiler["assumptions"].items()) + [("type", unitMap["type"])] ) 
					# boilerInputBPData =  dict(list(fuelData.items()) + list(realtimeBPData.items()) + list(boiler["assumptions"].items()) + [("type", mapping["type"])] ) 
					# boilerInputDesignData =  dict(list(fuelDesignData.items()) + list(realtimeDesignData.items()) + list(boiler["assumptions"].items()) + list(boiler["loiDesign"].items()) + [("type", mapping["type"])] ) 
				
					#print("boilerInputDataJson") 
					# print(json.dumps(fuelDesignData, indent=4))
					# print(json.dumps(realtimeDesignData, indent=4))
					#print(json.dumps(fuelDesignData, indent=4))
					#print("boilerInputDesignDataJson")
					#print(json.dumps(boilerInputDesignData, indent=4))
					#print("boilerInputBPData")
					#print(json.dumps(boilerInputBPData, indent=4))
					
					
					
					# tmp = [boilerInputData, boilerInputBPData, boilerInputDesignData]
					tmp = [boilerInputData]

					
					# inputDf = pd.DataFrame()
					# inputDf = pd.read_json(json.dumps(tmp))
					# inputDf['inputType'] = ['realTime', 'bestAchieved', 'design']
					# inputDf.to_csv(str(unitId + "_input.csv"))
					#print inputDf
					# res = request.json
					# print "in effBOilertype, ********"
					# print res
					if "type" not in boilerInputData:
						return json.dumps({"error" : "Boiler efficiency loss type required for efficiency calculations"}), 400
					else:
						if boilerInputData["type"] == "type1":
							boilerEfficiency = boilerEfficiencyType1(boilerInputData)
						elif boilerInputData["type"] == "type2":
							boilerEfficiency = boilerEfficiencyType2(boilerInputData)
						elif boilerInputData["type"] == "type3":
							boilerEfficiency = boilerEfficiencyType3(boilerInputData)
						elif boilerInputData["type"] == "type4":
							boilerEfficiency = boilerEfficiencyType4(boilerInputData)
						elif boilerInputData["type"] == "type5":
							boilerEfficiency = boilerEfficiencyType5(boilerInputData)
						elif boilerInputData["type"] == "type6":
							boilerEfficiency = boilerEfficiencyType6(boilerInputData)
						elif boilerInputData["type"] == "type7":
							boilerEfficiency = boilerEfficiencyType7(boilerInputData)
						elif boilerInputData["type"] == "type8":
							boilerEfficiency = boilerEfficiencyType8(boilerInputData)
						elif boilerInputData["type"] == "type9":
							boilerEfficiency = boilerEfficiencyType9(boilerInputData)        
						elif boilerInputData["type"] == "type10":
							boilerEfficiency = boilerEfficiencyType10(boilerInputData)
						elif boilerInputData["type"] == "type11":
							boilerEfficiency = boilerEfficiencyType11(boilerInputData)
						elif boilerInputData["type"] == "type12":
							boilerEfficiency = boilerEfficiencyType12(boilerInputData)
						elif boilerInputData["type"] == "type13":
							boilerEfficiency = boilerEfficiencyType13(boilerInputData) 
						elif boilerInputData["type"] == "type14":
							boilerEfficiency = boilerEfficiencyType14(boilerInputData) 
						elif boilerInputData["type"] == "type15":
							boilerEfficiency = boilerEfficiencyType15(boilerInputData)
						elif boilerInputData["type"] == "type16":
							boilerEfficiency = boilerEfficiencyType16(boilerInputData) 
						elif boilerInputData["type"] == "type17":
							boilerEfficiency = boilerEfficiencyType17(boilerInputData)
						elif boilerInputData["type"] == "type18":
							boilerEfficiency = boilerEfficiencyType18(boilerInputData)
						else:
							print(json.dumps({"error" : "Boiler efficiency loss type unavailable for efficiency calculations"}), 400)          



					# boilerEfficiency = requests.post(effURL+"boiler",json=boilerInputData)
					# if boilerEfficiency.status_code ==200:
					#     boilerEfficiency = json.loads(boilerEfficiency.content)

					# boilerBPefficiency = requests.post(effURL+"boiler",json=boilerInputBPData)
					# if boilerBPefficiency.status_code ==200:
					#     boilerBPefficiency = json.loads(boilerBPefficiency.content)
					
					# boilerDesignEfficiency = requests.post(effURL+"boiler",json=boilerInputDesignData)
					# if boilerDesignEfficiency.status_code ==200:
					#     boilerDesignEfficiency = json.loads(boilerDesignEfficiency.content)
					# else:
					#     print(boilerDesignEfficiency.text)

					# print "STopping here"
					#print json.dumps(boilerInputData)
					# print "boilerEfficiency"
					print (json.dumps(boilerEfficiency,indent=4))
					boilerEfficiency = json.dumps(boilerEfficiency)

	return boilerEfficiency, 200

# Function for Coal Flow 
@app.route('/efficiency/coalCal', methods=['POST'])
def coalFlowCalculation():
	res = request.json
	# print "printing res in coalflowcalc"
	# print res
	for i in ["boilerSteamFlow", "msTemp", "msPres", "fwTemp", "coalGCV", "boilerEfficiency"]:
		if str(i) not in res:
			return json.dumps({"error" : str(i) + " missing or '0' found"}), 400
	
	result = {'coalFlow' : 0, 'costOfFuel' : 0}
	mssteam = IAPWS97(T=(res["msTemp"] + 273), P=(res["msPres"] * 0.0980665))
	fwsteam = IAPWS97(T=(res["fwTemp"] + 273), x=0)
	entDiff = (mssteam.h / 4.1868) - (fwsteam.h / 4.1868)
	result["entDiff"] = entDiff
	landingCost = res["landingCost"] if res.get("landingCost") else 2500
	if (res["boilerSteamFlow"] != 0) or (res["boilerEfficiency"] != 0):
		coalFlow = (res["boilerSteamFlow"] * entDiff) / (res["boilerEfficiency"] * res["coalGCV"])
		result['coalFlow'] = np.round(coalFlow,4)
		result['costOfFuel'] = landingCost * result['coalFlow']
		result['costPerUnitSteam'] = result["costOfFuel"] / res["boilerSteamFlow"]
		return result
	else:
		return result
		

def coalFlowCalculationNoRequest(res):
	#print res
	for i in ["boilerSteamFlow", "msTemp", "msPres", "fwTemp", "coalGCV", "boilerEfficiency"]:
		if str(i) not in res:
			return json.dumps({"error" : str(i) + " missing or '0' found"}), 400
	
	result = {'coalFlow' : 0, 'costOfFuel' : 0}
	mssteam = IAPWS97(T=(res["msTemp"] + 273), P=(res["msPres"] * 0.0980665))
	fwsteam = IAPWS97(T=(res["fwTemp"] + 273), x=0)
	entDiff = (mssteam.h / 4.1868) - (fwsteam.h / 4.1868)
	result["entDiff"] = entDiff
	landingCost = res["landingCost"] if res.get("landingCost") else 2500
	if (res["boilerSteamFlow"] != 0) or (res["boilerEfficiency"] != 0):
		coalFlow = (res["boilerSteamFlow"] * entDiff) / (res["boilerEfficiency"] * res["coalGCV"])
		result['coalFlow'] = np.round(coalFlow,4)
		result['costOfFuel'] = landingCost * result['coalFlow']
		result['costPerUnitSteam'] = result["costOfFuel"] / res["boilerSteamFlow"]
		return result
	else:
		return result


def thr_pressureInMpa_calcs(res):
		res["totalShSprayWater"] = res["ShSprayWater01"] + res["ShSprayWater02"]
		res["enthalpyMS"] = IAPWS97(T=(res["steamTempMS"] + 273), P=(res["steamPressureMS"])).h
		res["enthalpyFW"] = IAPWS97(T=(res["FWFinalTemp"] + 273), P=(res["FWFinalPress"])).h


		res["HptSteamExhaustEnthalpy"] = IAPWS97(T=(res["HptExhaustTemp"] + 273), P=(res["HptExhaustPressure"])).h
		res["IptInletSteamEnthalpy"] = IAPWS97(T=(res["IptInletSteamTemp"] + 273), P=(res["IptInletSteamPress"])).h
		res["FeedWaterInletBeforeEcoEnthalpy"] = IAPWS97(T=(res["FWFinalTemp"] + 273), P=(res["FWFinalPress"])).h

		if res["totalShSprayWater"] > 0.0:
			res["ShSprayWaterEnthalpy"] = (IAPWS97(T=(res["ShRhSprayWaterTemp"] + 273), P=(res["FWFinalPress"])).h) + res["SprayWaterEnthalpyConstant"]
		else:
			res["ShSprayWaterEnthalpy"] = res["SprayWaterEnthalpyConstant"]

		if res["RhSprayWater"] > 0.0:
			res["RhSprayWaterEnthalpy"] = (IAPWS97(T=(res["ShRhSprayWaterTemp"] + 273), P=(res["FWFinalPress"])).h) + res["SprayWaterEnthalpyConstant"]
		else:
			res["RhSprayWaterEnthalpy"] = res["SprayWaterEnthalpyConstant"]
		
		res["FeedWaterInletToHph8Enthalpy"] = IAPWS97(T=(res["FeedWaterInletTempToHph8"] + 273), P=(res["FWFinalPress"])).h + res["FeedWaterInletToHph8EnthalpyConstant"]
		res["FeedWaterOutletToHph8Enthalpy"] = IAPWS97(T=(res["FeedWaterOutletTempToHph8"] + 273), P=(res["FWFinalPress"])).h + res["FeedWaterOutletToHph8EnthalpyConstant"]
		res["ExtractionSteamHph8Enthalpy"] = IAPWS97(T=(res["ExtractionSteamTempHph8"] + 273), P=(res["ExtractionSteamPressureHph8"])).h + res["ExtractionSteamHph8EnthalpyConstant"]
		res["DripHph8Enthalpy"] = IAPWS97(T=(res["DripTemperatureHph8"] + 273), P=(res["ExtractionSteamPressureHph8"])).h
		res["ExtractionSteamFlowHph8"] = res["FeedWaterFlow"] * (res["FeedWaterOutletToHph8Enthalpy"] - res["FeedWaterInletToHph8Enthalpy"]) / (res["ExtractionSteamHph8Enthalpy"] - res["DripHph8Enthalpy"])

		if res["ExtractionSteamPressureHph8"] < 1.0: #shudown conditon of HPH here
			res["ExtractionSteamFlowHph8"] = 0.0


		res["FeedWaterInletToHph7Enthalpy"] = IAPWS97(T=(res["FeedWaterInletTempToHph7"] + 273), P=(res["FWFinalPress"])).h + res["FeedWaterInletToHph7EnthalpyConstant"]
		res["FeedWaterOutletToHph7Enthalpy"] = res["FeedWaterInletToHph8Enthalpy"]
		res["ExtractionSteamHph7Enthalpy"] = IAPWS97(T=(res["ExtractionSteamTempHph7"] + 273), P=(res["ExtractionSteamPressureHph7"])).h + res["ExtractionSteamHph7EnthalpyConstant"]
		res["DripHph7Enthalpy"] = IAPWS97(T=(res["DripTemperatureHph7"] + 273), P=(res["ExtractionSteamPressureHph7"])).h + res["DripHph7EnthalpyConstant"]


		# print ("\n\n")
		# print (res["FeedWaterFlow"], res["FeedWaterOutletToHph7Enthalpy"], res["FeedWaterInletToHph7Enthalpy"], res["ExtractionSteamFlowHph8"], res["DripHph8Enthalpy"], res["DripHph7Enthalpy"], res["ExtractionSteamHph7Enthalpy"], res["DripHph7Enthalpy"])
		# print ("\n\n")

		res["ExtractionSteamFlowHph7"] = (res["FeedWaterFlow"] * (res["FeedWaterOutletToHph7Enthalpy"] - res["FeedWaterInletToHph7Enthalpy"]) - res["ExtractionSteamFlowHph8"] * (res["DripHph8Enthalpy"] - res["DripHph7Enthalpy"])) / (res["ExtractionSteamHph7Enthalpy"] - res["DripHph7Enthalpy"]) - 0.08

		# print (res["ExtractionSteamFlowHph7"])

		if res["ExtractionSteamPressureHph7"] < 0.5: #shudown conditon of HPH here
			res["ExtractionSteamFlowHph7"] = 0.0

		try:
			res["FeedWaterInletToHph6Enthalpy"] = IAPWS97(T=(res["FeedWaterInletTempToHph6"] + 273), P=(res["FWFinalPress"])).h - res["FeedWaterInletToHph6EnthalpyConstant"]
			res["FeedWaterOutletToHph6Enthalpy"] = IAPWS97(T=(res["FeedWaterInletTempToHph7"] + 273), P=(res["FWFinalPress"])).h - res["FeedWaterOutletToHph6EnthalpyConstant"]
			res["ExtractionSteamHph6Enthalpy"] = IAPWS97(T=(res["ExtractionSteamTempHph6"] + 273), P=(res["ExtractionSteamPressureHph6"])).h + res["ExtractionSteamHph6EnthalpyConstant"]
			res["DripHph6Enthalpy"] = IAPWS97(T=(res["DripTemperatureHph6"] + 273), P=(res["ExtractionSteamPressureHph6"])).h + res["DripHph6EnthalpyConstant"]

			res["ExtractionSteamFlowHph6"] = (res["FeedWaterFlow"] * (res["FeedWaterOutletToHph6Enthalpy"] - res["FeedWaterInletToHph6Enthalpy"]) - (res["ExtractionSteamFlowHph8"] + res["ExtractionSteamFlowHph7"]) * (res["DripHph7Enthalpy"] - res["DripHph6Enthalpy"])) / (res["ExtractionSteamHph6Enthalpy"] - res["DripHph6Enthalpy"]) - 0.259
		except Exception as e:
			print (e, "data error in HPH 6 calculations")
			res["ExtractionSteamFlowHph6"] = 0.0
			res["FeedWaterInletToHph6Enthalpy"] = 0.0
			res["FeedWaterOutletToHph6Enthalpy"] = 0.0
			res["ExtractionSteamHph6Enthalpy"] = 0.0
			res["DripHph6Enthalpy"] = 0.0
			pass

		if res["ExtractionSteamPressureHph6"] < 0.5: #shudown conditon of HPH here
			res["ExtractionSteamFlowHph6"] = 0.0


		try:
			res["condensateInletHph5Enthalpy"] = IAPWS97(T=(res["condensateInletTempHph5"] + 273), P=(res["condensateInletWaterPress"])).h
			res["condensateOutletHph5Enthalpy"] = IAPWS97(T=(res["FeedWaterInletTempToHph6"] + 273), P=(12.74)).h
			res["ExtractionSteamHph5Enthalpy"] = IAPWS97(T=(res["extractionSteamTempHph5"] + 273), P=(res["extractionSteamPressureHph5"])).h

		# print ("\n\n")
		# print (res["condensateFlow"], res["condensateOutletHph5Enthalpy"], res["condensateInletHph5Enthalpy"], res["ExtractionSteamFlowHph8"], res["ExtractionSteamFlowHph7"], res["ExtractionSteamFlowHph6"], res["DripHph6Enthalpy"], res["condensateOutletHph5Enthalpy"], res["ExtractionSteamHph5Enthalpy"], res["condensateOutletHph5Enthalpy"])
		# print ("\n\n")

			res["extractionSteamFlowHph5"] = (res["condensateFlow"] * (res["condensateOutletHph5Enthalpy"]  - res["condensateInletHph5Enthalpy"]) - (res["ExtractionSteamFlowHph8"] + res["ExtractionSteamFlowHph7"] + res["ExtractionSteamFlowHph6"] + 0.834 + 3.81) * (res["DripHph6Enthalpy"] - res["condensateOutletHph5Enthalpy"])) / (res["ExtractionSteamHph5Enthalpy"] - res["condensateOutletHph5Enthalpy"]) - 0.02
		except Exception as e:
			print (e, "error in HPG 5 calculations")
			res["extractionSteamFlowHph5"] = 0.0
			res["condensateInletHph5Enthalpy"] = 0.0
			res["condensateOutletHph5Enthalpy"] = 0.0
			res["ExtractionSteamHph5Enthalpy"] = 0.0
			pass

		if res["extractionSteamPressureHph5"] < 0.3:
			res["extractionSteamFlowHph5"] = 0.0

		res["finalFeedWaterFlow_CalculatedFromCondensateFlow"] = res["extractionSteamFlowHph5"] + res["condensateFlow"] + res["ExtractionSteamFlowHph6"] + res["ExtractionSteamFlowHph7"] + res["ExtractionSteamFlowHph8"] - res["RhSprayWater"] - res["totalShSprayWater"] + 0.011

		res["computedMainSteamFlow_computedFWFlow"] = res["finalFeedWaterFlow_CalculatedFromCondensateFlow"] + res["totalShSprayWater"]

		res["HrhSteamFlow"] = res["steamFlowMS"] - res["ExtractionSteamFlowHph7"] - res["ExtractionSteamFlowHph8"] - res["GlandSteamFlow_LeakOff_InterStageLeakage"]

		res["turbineHeatRate"] = ((res["steamFlowMS"] * (res["enthalpyMS"] - res["enthalpyFW"]) + res["HrhSteamFlow"] * (res["IptInletSteamEnthalpy"] - res["HptSteamExhaustEnthalpy"]) + res["totalShSprayWater"] * (res["enthalpyFW"] - res["ShSprayWaterEnthalpy"]) + res["RhSprayWater"] *(res["IptInletSteamEnthalpy"] - res["RhSprayWaterEnthalpy"])) / res["load"])  / 4.186 

		# res["turbineHeatRate"] = res["turbineHeatRate"] / 4.186 

		# print (json.dumps(res, indent=4))

		return res



# Function for Turbine HRT 
@app.route('/efficiency/thr', methods=['POST'])
def THRCalculation():
	res = request.json
	for i in ["steamFlowMS", "steamPressureMS", "steamTempMS", "FWFinalTemp", "FWFinalPress", "load"]:
		try:
			if i in ["steamTempMS", "FWFinalTemp"]:
				if res[i] < 30:
					return json.dumps({"error" : "bad request"}), 400

			if res[i] == 0:
				return json.dumps({"error" : str(i) + " value is '0'"}), 400

		except Exception as e:
			print(e)
			pass 
	# for i in ["steamFlowMS", "steamPressureMS", "steamTempMS", "FWFinalTemp", "FWFinalPress", "load"]:
	#     if i in ["steamTempMS", "FWFinalTemp"]:
	#         if res[i] < 50:
	#             return json.dumps({"error" : "bad request"}), 400

	#     if (i not in res) or (res[i] == 0):
	#         return json.dumps({"error" : str(i) + " missing or '0' found"}), 400
	
	if str(res["category"]) == "cogent":
		make = {}
		mssteam = IAPWS97(T=(res["steamTempMS"] + 273), P=(res["steamPressureMS"] * 0.0980665))
		fwsteam = IAPWS97(T=(res["FWFinalTemp"] + 273), P=(res["FWFinalPress"] * 0.0980665))
		prosteam = IAPWS97(T=(res["ProSteamTemp"] + 273), P=(res["ProSteamPress"] * 0.0980665))
		makeupsteam = IAPWS97(T=(68 + 273), P=(10 * 0.0980665))
		enthalpyMS, enthalpyFW, enthalpyProSteam, enthalpyMakeup = mssteam.h / 4.1868, fwsteam.h / 4.1868, prosteam.h / 4.1868, makeupsteam.h / 4.1868
		print ("enthalpyMS", enthalpyMS)
		print ("enthalpyFW", enthalpyFW)
		print ("enthalpyProSteam", enthalpyProSteam)
		print ("enthalpyMakeup", enthalpyMakeup)
		make["steamFlowMS"] = res["steamFlowMS"]
		make["enthalpyMS"] = enthalpyMS
		make["enthalpyFW"] = enthalpyFW
		make["FWFlow"] = res["FWFlow"]
		if "processFlow" in res:
			print(":::::IN")
			make["processFlow"] = res["processFlow"]
		else :
			print("::::ELSE")
			res["processFlow"] = res["makeUpFlow"]
		make["enthalpyProSteam"] = enthalpyProSteam
		make["enthalpyMakeup"] = enthalpyMakeup
		# thr = (res["steamFlowMS"] * enthalpyMS) - (res["FWFlow"] * enthalpyFW) - (res["processFlow"] * (enthalpyProSteam - enthalpyMakeup))
		if "processFlow" in res:
			thr = (res["steamFlowMS"] * enthalpyMS) - (res["FWFlow"] * enthalpyFW) - (res["processFlow"] * enthalpyProSteam) + (res["makeUpFlow"] * enthalpyMakeup)
		else :
			thrEntSum1=enthalpyMS+enthalpyMakeup
			thrEntSum2=enthalpyFW+enthalpyProSteam
			thr = thrEntSum1-thrEntSum2

		thr = thr / (res["load"])

		return {"turbineHeatRate" : thr}
	
	elif str(res["category"]) == "ingest":
		make = {}
		mssteam = IAPWS97(T=(res["steamTempMS"] + 273), P=(res["steamPressureMS"] * 0.0980665))
		igsteam = IAPWS97(T=(res["ingestSteamTemp"] + 273), P=(res["ingestSteamPressure"] * 0.0980665))
		dissteam = IAPWS97(T=(res["dischargeSteamTemp"] + 273), P=(11.5 * 0.0980665))
		makeupsteam = IAPWS97(T=(40 + 273), P=(10 * 0.0980665))
		enthalpyMS, enthalpyIG, enthalpyDisSteam, enthalpyMakeup = mssteam.h / 4.1868, igsteam.h / 4.1868, dissteam.h / 4.1868, makeupsteam.h / 4.1868
		# print "enthalpyMS", enthalpyMS
		# print "enthalpyIG", enthalpyIG
		# print "enthalpyDisSteam", enthalpyDisSteam
		# print "enthalpyMakeup", enthalpyMakeup
		make["steamFlowMS"] = res["steamFlowMS"]
		make["ingestSteamFlow"] = res["ingestSteamFlow"]
		make["enthalpyMS"] = enthalpyMS
		make["enthalpyIG"] = enthalpyIG
		make["enthalpyDisSteam"] = enthalpyDisSteam
		make["enthalpyMakeup"] = enthalpyMakeup
		thr = ((make["steamFlowMS"] * (enthalpyMS - enthalpyDisSteam)) + (make["ingestSteamFlow"] * (enthalpyIG - enthalpyDisSteam)))
		thr = thr / (res["load"])

		return {"turbineHeatRate" : thr}

	elif str(res["category"]) == "ingest2":
		print("in ingest2")
		make = {}
		mssteam = IAPWS97(T=(res["steamTempMS"] + 273), P=(res["steamPressureMS"] * 0.0980665))
		igsteam = IAPWS97(T=(res["ingestSteamTemp"] + 273), P=(res["ingestSteamPressure"] * 0.0980665))
		condenseSteam = IAPWS97(T=(res["condensateSteamTemp"] + 273), P=(res["condensateteamPressure"] * 0.0980665))
		makeupsteam = IAPWS97(T=(35 + 273), P=(2.1 * 0.0980665))
		enthalpyMS, enthalpyIG, enthalpycondenseSteam, enthalpyMakeup = mssteam.h / 4.1868, igsteam.h / 4.1868, condenseSteam.h / 4.1868, makeupsteam.h / 4.1868
		# print "enthalpyMS", enthalpyMS
		# print "enthalpyIG", enthalpyIG
		# print "enthalpyDisSteam", enthalpyDisSteam
		# print "enthalpyMakeup", enthalpyMakeup
		make["steamFlowMS"] = res["steamFlowMS"]
		make["ingestSteamFlow"] = res["ingestSteamFlow"]
		make["enthalpyMS"] = enthalpyMS
		make["enthalpyIG"] = enthalpyIG
		make["enthalpyDisSteam"] = enthalpycondenseSteam
		make["enthalpyMakeup"] = enthalpyMakeup
		thr = ((make["steamFlowMS"] * (enthalpyMS - enthalpycondenseSteam)) + (make["ingestSteamFlow"] * (enthalpyIG - enthalpycondenseSteam)))
		thr = thr / (res["load"])

		return {"turbineHeatRate" : thr}

	elif str(res["category"]) == "cogent2":
		steam1 = IAPWS97(T=(res["steamTempMS"] + 273), P=(res["steamPressureMS"] * 0.0980665))
		steam2 = IAPWS97(T=(res["FWFinalTemp"] + 273), P=(res["FWFinalPress"] * 0.0980665))
		# if "FWFinalPress" in res:
		#     steam2 = IAPWS97(T=(res["FWFinalTemp"] + 273), P=(res["FWFinalPress"] * 0.0980665))
		# else:
		#     steam2 = IAPWS97(T=(res["FWFinalTemp"] + 273), P=(10.135 * 0.0980665))
		
		MakeupFlw = IAPWS97(T=(35 + 273), P=(10.135 * 0.0980665))
		enthalpyMS, enthalpyFW,enthalpyMakeupFlw = steam1.h / 4.1868, steam2.h / 4.1868, MakeupFlw.h / 4.1868
		# print "ENthalpy : ", enthalpyMS, enthalpyFW, res["steamFlowMS"], (res["steamFlowMS"] * (enthalpyMS + enthalpyMakeupFlw - enthalpyFW)) / res["load"], res["FWFinalTemp"] + 273, res["FWFinalPress"]
		#note fwflow is replaced with steamflowMS for mcl2 and cogent2 holds good for mcl2
		return {"turbineHeatRate" : ((res["steamFlowMS"] * enthalpyMS) +(res["makeUpFlow"]* enthalpyMakeupFlw) - (res["steamFlowMS"] * enthalpyFW)) / res["load"]}
			
	elif str(res["category"]) == "cogent3":
		print("_________cogent3______")
		make = {}
		stgSteam = IAPWS97(T=(res["stgIlTemp"] + 273), P=(res["stgIlPres"] * 0.0980665))
		hpProSteam = IAPWS97(T=(res["hpProIlTemp"] + 273), P=(res["hpProIlPres"] * 0.0980665))
		lp1ProSteam = IAPWS97(T=(res["lpPro1IlTemp"] + 273), P=(10.2 * 0.0980665))
		lp2ProSteam = IAPWS97(T=(res["lpPro2IlTemp"] + 273), P=(9.7 * 0.0980665))
		fwsteam = IAPWS97(T=(res["fwTemp"] + 273), P=(res["fwPres"] * 0.0980665))
		hpLpConSteam = IAPWS97(T=(res["hpLpConReturnTemp"] + 273), P=(10.0 * 0.0980665))
		mkpSteam = IAPWS97(T=(35.0 + 273), P=(10.0 * 0.0980665))
		
		stgSteamEnthalpy = (res["steamFlowMS"]) *stgSteam.h / 4.1868
		hpProSteamEnthalpy =(res["hpProIlFlow"])*hpProSteam.h / 4.1868
		lp1ProSteamEnthalpy =(res["lpPro1IlFlow"])*lp1ProSteam.h / 4.1868
		lp2ProSteamEnthalpy =(res["lpPro2IlFlow"])*lp2ProSteam.h / 4.1868
		fwSteamEnthalpy = (res["fwFlow"])*fwsteam.h / 4.1868
		hpLpConSteamEnthalpy=(res["hpLpConReturnFlow"])*hpLpConSteam.h / 4.1868
		mkpSteamEnthalpy= (res["makeupIlFlow"])*mkpSteam.h / 4.1868
		thrEntSum1 = stgSteamEnthalpy + hpLpConSteamEnthalpy + mkpSteamEnthalpy
		thrEntSum2 = hpProSteamEnthalpy + lp1ProSteamEnthalpy + lp2ProSteamEnthalpy + fwSteamEnthalpy
		thr = (thrEntSum1 - thrEntSum2) / res["load"]

		return {"turbineHeatRate" : thr}
			

	elif str(res["category"]) == "cogent4":
		print("_________cogent4______")
		make = {}
		stgSteam = IAPWS97(T=(res["stgIlTemp"] + 273), P=(res["stgIlPres"] * 0.0980665))
		if "hpProIlTemp" in res :
			hpProSteam = IAPWS97(T=(res["hpProIlTemp"] + 273), P=(res["hpProIlPres"] * 0.0980665))
			lpProSteam = IAPWS97(T=(80 + 273), P=(9.8 * 0.0980665))
			if "lpPro1IlTemp" in res:
				lpProSteam = IAPWS97(T=(res["lpPro1IlTemp"] + 273), P=(res["lpPro1IlPres"] * 0.0980665))
			if "hpProIlFlow" in res :
				hpProSteamEnthalpy =(res["hpProIlFlow"])*hpProSteam.h / 4.1868
			else:
				hpProSteamEnthalpy =(res["steamFlowMS"])*hpProSteam.h / 4.1868
			lpProSteamEnthalpy =(res["lpPro1IlFlow"])*lpProSteam.h / 4.1868
		# lp2ProSteam = IAPWS97(T=(res["lpPro2IlTemp"] + 273), P=(9.7 * 0.0980665))
		fwsteam = IAPWS97(T=(res["fwTemp"] + 273), P=(res["fwPres"] * 0.0980665))
		# hpLpConSteam = IAPWS97(T=(res["hpLpConReturnTemp"] + 273), P=(10.0 * 0.0980665))
		# mkpSteam = IAPWS97(T=(res["makeupIlTemp"] + 273), P=(9.8 * 0.0980665))
		if "makeupIlTemp" in res :
			mkpSteam = IAPWS97(T=(res["makeupIlTemp"] + 273), P=(9.8 * 0.0980665))
			mkpSteamEnthalpy= (res["makeupIlFlow"])*mkpSteam.h / 4.1868
		else :
			mkpSteamEnthalpy=0
		stgSteamEnthalpy = (res["steamFlowMS"]) *stgSteam.h / 4.1868
		# lp2ProSteamEnthalpy =(res["lpPro2IlFlow"])*lp2ProSteam.h / 4.1868
		fwSteamEnthalpy = (res["fwFlow"])*fwsteam.h / 4.1868
		# hpLpConSteamEnthalpy=(res["hpLpConReturnFlow"])*hpLpConSteam.h / 4.1868
		# mkpSteamEnthalpy= (res["makeupIlFlow"])*mkpSteam.h / 4.1868
		if "hpProIlTemp" in res :
			thrEntSum1 = stgSteamEnthalpy + lpProSteamEnthalpy + mkpSteamEnthalpy
			thrEntSum2 = hpProSteamEnthalpy + fwSteamEnthalpy
		else:
			thrEntSum1 = stgSteamEnthalpy + mkpSteamEnthalpy
			thrEntSum2 = fwSteamEnthalpy

		thr = (thrEntSum1-thrEntSum2 ) / res["load"]

		return {"turbineHeatRate" : thr}

	elif str(res["category"]) == "cogent5":
		print("_________cogent5______")
		make = {}
		stgSteam = IAPWS97(T=(res["stgIlTemp"] + 273), P=(res["stgIlPres"] * 0.0980665))
		if "hpProIlTemp" in res :
			hpProSteam = IAPWS97(T=(res["hpProIlTemp"] + 273), P=(res["hpProIlPres"] * 0.0980665))
			lpProSteam = IAPWS97(T=(res["lpProIlTemp"] + 273), P=(9.8 * 0.0980665))
			if "hpProIlFlow" in res :
				hpProSteamEnthalpy =(res["hpProIlFlow"])*hpProSteam.h / 4.1868
			else:
				hpProSteamEnthalpy =(res["steamFlowMS"])*hpProSteam.h / 4.1868
			lpProSteamEnthalpy =(res["lpPro1IlFlow"])*lpProSteam.h / 4.1868
		mkpSteam = IAPWS97(T=(res["makeupIlTemp"] + 273), P=(9.8 * 0.0980665))
		stgSteamEnthalpy = (res["steamFlowMS"]) *stgSteam.h / 4.1868
		mkpSteamEnthalpy= (res["makeupIlFlow"])*mkpSteam.h / 4.1868
		if "hpProIlTemp" in res :
			thrEntSum1 = stgSteamEnthalpy + lpProSteamEnthalpy + mkpSteamEnthalpy
			thrEntSum2 = hpProSteamEnthalpy 
		else:
			fwSteamEnthalpy=0
			thrEntSum1 = stgSteamEnthalpy + mkpSteamEnthalpy
			thrEntSum2 = fwSteamEnthalpy

		thr = (thrEntSum1-thrEntSum2 ) / res["load"]

		return {"turbineHeatRate" : thr}
	
	elif str(res["category"]) == "cogent6":
		print("in ingest2")
		make = {}
		stgSteam = IAPWS97(T=(res["stgIlTemp"] + 273), P=(res["stgIlPres"] * 0.0980665))
		turbineExhaust = IAPWS97(T=(res["turbineExhaustSteamTemp"] + 273), P=(res["turbineExhaustSteamPressure"] * 0.0980665))
		# PRDS = IAPWS97(T=(res["prdsSteamTemp"] + 273), P=(res["prdsSteamPressure"] * 0.0980665))
		if "makeupIlTemp" in res:
			mkpSteam = IAPWS97(T=(res["makeupIlTemp"] + 273), P=(res['makeupIlPressure'] * 0.0980665))
			mkpSteamEnthalpy= (res["makeupIlFlow"])*mkpSteam.h / 4.1868
		stgSteamEnthalpy = (res["steamFlowMS"]) *stgSteam.h / 4.1868
		turbineExhaustSteamEnthalpy = (res["steamFlowMS"])*turbineExhaust.h / 4.1868
		# PRDSEnthalpy= (res["prdsFlow"])*PRDS.h / 4.1868
		
		if "makeupIlTemp" in res:
			thrEntSum1 = stgSteamEnthalpy + mkpSteamEnthalpy
			thrEntSum2 = turbineExhaustSteamEnthalpy
		else :
			thrEntSum1 = stgSteamEnthalpy 
			thrEntSum2 = turbineExhaustSteamEnthalpy


		thr = (thrEntSum1-thrEntSum2 ) / res["load"]
		return {"turbineHeatRate" : thr}

	elif str(res["category"]) == "cogent7":
		print("_________cogent7______")
		make = {}
		stgSteam = IAPWS97(T=(res["stgIlTemp"] + 273), P=(res["stgIlPres"] * 0.0980665))
		hpProSteam = IAPWS97(T=(res["hpProIlTemp"] + 273), P=(res["hpProIlPres"] * 0.0980665))
		hpProSteamEnthalpy =(res["hpProIlFlow"])*hpProSteam.h / 4.1868
		mkpDeaeratorSteam = IAPWS97(T=(res["MakeupDeaeratorIlTemp"] + 273), P=(res["MakeupDeaeratorPres"] * 0.0980665))
		mkpHotwellSteam = IAPWS97(T=(res["MakeupDeaeratorIlTemp"] + 273), P=(res["MakeupDeaeratorPres"] * 0.0980665))
		stgSteamEnthalpy = (res["steamFlowMS"]) *stgSteam.h / 4.1868
		mkpDeaeratorSteamEnthalpy= (res["MakeupDeaeratorFlow"])*mkpDeaeratorSteam.h / 4.1868
		mkpHotwellSteamEnthalpy= (res["makeupHotwellFlow"])*mkpHotwellSteam.h / 4.1868
		fwsteam = IAPWS97(T=(res["fwTemp"] + 273), P=(res["fwPres"] * 0.0980665))
		fwSteamEnthalpy = (res["fwFlow"])*fwsteam.h / 4.1868
		print("makeupdearatorenthalpy",mkpDeaeratorSteamEnthalpy)
		print("mkpHotwellSteamEnthalpy",mkpHotwellSteamEnthalpy)

		thrEntSum1 = stgSteamEnthalpy + mkpDeaeratorSteamEnthalpy+mkpHotwellSteamEnthalpy
		thrEntSum2 = fwSteamEnthalpy
		thr = (thrEntSum1-thrEntSum2 ) / res["load"]

		return {"turbineHeatRate" : thr}

	elif str(res["category"]) == "cogent8":
		print("_________cogent8______")
		make = {}
		stgSteam = IAPWS97(T=(res["stgIlTemp"] + 273), P=(res["stgIlPres"] * 0.0980665))
		try:
			Process1Steam = IAPWS97(T=(res["Process1Temp"] + 273), P=(res["Process1Pres"] * 0.0980665))
			Process1SteamEnthalpy =(res["ProcessFlow1"])*Process1Steam.h / 4.1868
		except :
			Process1SteamEnthalpy=0
		try:
			Process2Steam = IAPWS97(T=(res["Process2Temp"] + 273), P=(res["Process2Pres"] * 0.0980665))
			Process2SteamEnthalpy =(res["ProcessFlow2"])*Process2Steam.h / 4.1868
		except :
			Process2SteamEnthalpy=0
			
		fwsteam = IAPWS97(T=(res["fwTemp"] + 273), P=(res["fwPres"] * 0.0980665))
		ConDearatorSteam = IAPWS97(T=(res["CondDearatorTemp"] + 273), P=(res["CondDearatorPres"] * 0.0980665))
		mkpSteam = IAPWS97(T=(res["makeupTemp"] + 273), P=(res["makeupPres"] * 0.0980665))
		
		stgSteamEnthalpy = (res["steamFlowMS"]) *stgSteam.h / 4.1868
		fwSteamEnthalpy = (res["fwFlow"])*fwsteam.h / 4.1868
		ConDearatorSteamEnthalpy=(res["CondDearatorFlow"])*ConDearatorSteam.h / 4.1868
		mkpSteamEnthalpy= (res["makeupIlFlow"])*mkpSteam.h / 4.1868
		thrEntSum1 = stgSteamEnthalpy + ConDearatorSteamEnthalpy + mkpSteamEnthalpy
		thrEntSum2 = fwSteamEnthalpy + Process1SteamEnthalpy + Process2SteamEnthalpy
		thr = (thrEntSum1 - thrEntSum2) / res["load"]

		return {"turbineHeatRate" : thr}

	elif str(res["category"]) == "pressureInMpa":

		res = thr_pressureInMpa_calcs(res)
		return res
	
	elif str(res["category"]) == "pressureInKsc":
		# print (json.dumps(res, indent=4))
		res["totalShSprayWater"] = res["ShSprayWater01"] + res["ShSprayWater02"]
		res["enthalpyMS"] = IAPWS97(T=(res["steamTempMS"] + 273), P=((res["steamPressureMS"] * 0.0980665))).h
		res["enthalpyFW"] = IAPWS97(T=(res["FWFinalTemp"] + 273), P=((res["FWFinalPress"] * 0.0980665))).h


		res["HptSteamExhaustEnthalpy"] = IAPWS97(T=(res["HptExhaustTemp"] + 273), P=((res["HptExhaustPressure"] * 0.0980665))).h
		res["IptInletSteamEnthalpy"] = IAPWS97(T=(res["IptInletSteamTemp"] + 273), P=((res["IptInletSteamPress"] * 0.0980665))).h
		res["FeedWaterInletBeforeEcoEnthalpy"] = IAPWS97(T=(res["FWFinalTemp"] + 273), P=((res["FWFinalPress"] * 0.0980665))).h

		if res["totalShSprayWater"] > 0.0:
			res["ShSprayWaterEnthalpy"] = (IAPWS97(T=(res["ShRhSprayWaterTemp"] + 273), P=((res["FWFinalPress"] * 0.0980665))).h) + res["SprayWaterEnthalpyConstant"]
		else:
			res["ShSprayWaterEnthalpy"] = res["SprayWaterEnthalpyConstant"]

		if res["RhSprayWater"] > 0.0:
			res["RhSprayWaterEnthalpy"] = (IAPWS97(T=(res["ShRhSprayWaterTemp"] + 273), P=((res["FWFinalPress"] * 0.0980665))).h) + res["SprayWaterEnthalpyConstant"]
		else:
			res["RhSprayWaterEnthalpy"] = res["SprayWaterEnthalpyConstant"]
		
		res["FeedWaterInletToHph8Enthalpy"] = IAPWS97(T=(res["FeedWaterInletTempToHph8"] + 273), P=((res["FWFinalPress"] * 0.0980665))).h + res["FeedWaterInletToHph8EnthalpyConstant"]
		res["FeedWaterOutletToHph8Enthalpy"] = IAPWS97(T=(res["FeedWaterOutletTempToHph8"] + 273), P=((res["FWFinalPress"] * 0.0980665))).h + res["FeedWaterOutletToHph8EnthalpyConstant"]
		res["ExtractionSteamHph8Enthalpy"] = IAPWS97(T=(res["ExtractionSteamTempHph8"] + 273), P=((res["ExtractionSteamPressureHph8"] * 0.0980665))).h + res["ExtractionSteamHph8EnthalpyConstant"]
		res["DripHph8Enthalpy"] = IAPWS97(T=(res["DripTemperatureHph8"] + 273), P=(res["ExtractionSteamPressureHph8"])).h
		res["ExtractionSteamFlowHph8"] = res["FeedWaterFlow"] * (res["FeedWaterOutletToHph8Enthalpy"] - res["FeedWaterInletToHph8Enthalpy"]) / (res["ExtractionSteamHph8Enthalpy"] - res["DripHph8Enthalpy"])

		res["FeedWaterInletToHph7Enthalpy"] = IAPWS97(T=(res["FeedWaterInletTempToHph7"] + 273), P=((res["FWFinalPress"] * 0.0980665))).h + res["FeedWaterInletToHph7EnthalpyConstant"]
		res["FeedWaterOutletToHph7Enthalpy"] = res["FeedWaterInletToHph8Enthalpy"]
		res["ExtractionSteamHph7Enthalpy"] = IAPWS97(T=(res["ExtractionSteamTempHph7"] + 273), P=((res["ExtractionSteamPressureHph7"] * 0.0980665))).h + res["ExtractionSteamHph7EnthalpyConstant"]
		res["DripHph7Enthalpy"] = IAPWS97(T=(res["DripTemperatureHph7"] + 273), P=(res["ExtractionSteamPressureHph7"])).h + res["DripHph7EnthalpyConstant"]

	
		res["ExtractionSteamFlowHph7"] = (res["FeedWaterFlow"] * (res["FeedWaterOutletToHph7Enthalpy"] - res["FeedWaterInletToHph7Enthalpy"]) - res["ExtractionSteamFlowHph8"] * (res["DripHph8Enthalpy"] - res["DripHph7Enthalpy"])) / (res["ExtractionSteamHph7Enthalpy"] - res["DripHph7Enthalpy"]) - 0.08


		res["HrhSteamFlow"] = res["steamFlowMS"] - res["ExtractionSteamFlowHph7"] - res["ExtractionSteamFlowHph8"] - res["GlandSteamFlow_LeakOff_InterStageLeakage"]

		res["turbineHeatRate"] = ( res["steamFlowMS"] * (res["enthalpyMS"] - res["enthalpyFW"])
								+ res["HrhSteamFlow"] * (res["IptInletSteamEnthalpy"] - res["HptSteamExhaustEnthalpy"])
								+ res["totalShSprayWater"] * (res["enthalpyFW"] - res["ShSprayWaterEnthalpy"])
								+ res["RhSprayWater"] *(res["IptInletSteamEnthalpy"] - res["RhSprayWaterEnthalpy"])) / res["load"]

		res["turbineHeatRate"] = res["turbineHeatRate"] / 4.186      

		return res

	elif str(res["category"]) == "pressureInKsc1":
		res["totalShSprayWater"] = res["ShSprayWater01"] + res["ShSprayWater02"]
		res["enthalpyMS"] = IAPWS97(T=(res["steamTempMS"] + 273), P=((res["steamPressureMS"] * 0.0980665))).h
		print("enthalpyMS",res["enthalpyMS"])
		res["enthalpyFW"] = IAPWS97(T=(res["FWFinalTemp"] + 273), P=((res["FWFinalPress"] * 0.0980665))).h
		print("enthalpyFW",res["enthalpyFW"])
		res["HptSteamExhaustEnthalpy"] = IAPWS97(T=(res["HptExhaustTemp"] + 273), P=((res["HptExhaustPressure"] * 0.0980665))).h
		res["IptInletSteamEnthalpy"] = IAPWS97(T=(res["IptInletSteamTemp"] + 273), P=((res["IptInletSteamPress"] * 0.0980665))).h
		res["FeedWaterInletBeforeEcoEnthalpy"] = IAPWS97(T=(res["FWFinalTemp"] + 273), P=((res["FWFinalPress"] * 0.0980665))).h

		if res["totalShSprayWater"] > 0.0:
			res["ShSprayWaterEnthalpy"] = (IAPWS97(T=(res["ShRhSprayWaterTemp"] + 273), P=((res["FWFinalPress"] * 0.0980665))).h) + res["SprayWaterEnthalpyConstant"]
		else:
			res["ShSprayWaterEnthalpy"] = res["SprayWaterEnthalpyConstant"]

		if res["RhSprayWater"] > 0.0:
			res["RhSprayWaterEnthalpy"] = (IAPWS97(T=(res["ShRhSprayWaterTemp"] + 273), P=((res["FWFinalPress"] * 0.0980665))).h) + res["SprayWaterEnthalpyConstant"]
		else:
			res["RhSprayWaterEnthalpy"] = res["SprayWaterEnthalpyConstant"]

		res["FeedWaterInletToHph8Enthalpy"] = IAPWS97(T=(res["FeedWaterInletTempToHph6A"] + 273), P=((res["FWFinalPress"] * 0.0980665))).h + res["FeedWaterInletToHph8EnthalpyConstant"]
		res["FeedWaterOutletToHph8Enthalpy"] = IAPWS97(T=(res["FeedWaterOutletTempToHph6A"] + 273), P=((res["FWFinalPress"] * 0.0980665))).h + res["FeedWaterOutletToHph8EnthalpyConstant"]
		res["ExtractionSteamHph8Enthalpy"] = IAPWS97(T=(res["ExtractionSteamTempHph6A"] + 273), P=((res["ExtractionSteamPressureHph6A"] * 0.0980665))).h + res["ExtractionSteamHph8EnthalpyConstant"]
		res["DripHph8Enthalpy"] = IAPWS97(T=(res["DripTemperatureHph8"] + 273), P=(res["ExtractionSteamPressureHph6A"])).h
		res["ExtractionSteamFlowHph8"] = res["FeedWaterFlow"] * (res["FeedWaterOutletToHph8Enthalpy"] - res["FeedWaterInletToHph8Enthalpy"]) / (res["ExtractionSteamHph8Enthalpy"] - res["DripHph8Enthalpy"])

		res["FeedWaterInletToHph7Enthalpy"] = IAPWS97(T=(res["FeedWaterInletTempToHph6B"] + 273), P=((res["FWFinalPress"] * 0.0980665))).h + res["FeedWaterInletToHph7EnthalpyConstant"]
		res["FeedWaterOutletToHph7Enthalpy"] = res["FeedWaterInletToHph8Enthalpy"]
		res["ExtractionSteamHph7Enthalpy"] = IAPWS97(T=(res["ExtractionSteamTempHph6B"] + 273), P=((res["ExtractionSteamPressureHph6B"] * 0.0980665))).h + res["ExtractionSteamHph7EnthalpyConstant"]
		res["DripHph7Enthalpy"] = IAPWS97(T=(res["DripTemperatureHph7"] + 273), P=(res["ExtractionSteamPressureHph6B"])).h + res["DripHph7EnthalpyConstant"]

		res["ExtractionSteamFlowHph7"] = (res["FeedWaterFlow"] * (res["FeedWaterOutletToHph7Enthalpy"] - res["FeedWaterInletToHph7Enthalpy"]) - res["ExtractionSteamFlowHph8"] * (res["DripHph8Enthalpy"] - res["DripHph7Enthalpy"])) / (res["ExtractionSteamHph7Enthalpy"] - res["DripHph7Enthalpy"]) - 0.08
		res["steamFlowMS"] = res["FeedWaterFlow"] + res["totalShSprayWater"]

		res["HrhSteamFlow"] = res["steamFlowMS"] - res["ExtractionSteamFlowHph7"] - res["ExtractionSteamFlowHph8"] - res["GlandSteamFlow_LeakOff_InterStageLeakage"]

		res["turbineHeatRate"] = (res["FeedWaterFlow"] * (res["enthalpyMS"] - res["enthalpyFW"])
								+ res["totalShSprayWater"] * (res["enthalpyMS"] - res["ShSprayWaterEnthalpy"])
								+ res["HrhSteamFlow"] * (res["enthalpyFW"] - res["IptInletSteamEnthalpy"])
								+ res["RhSprayWater"] * (res["HptSteamExhaustEnthalpy"] - res["RhSprayWaterEnthalpy"])) / res["load"]
		return res

	elif str(res["category"]) == "lpg_type":
		print ("\n\ncame to lpg finally \n\n")
		print (res)
		steamEnthalpy = IAPWS97(T=(res["steamTempMS"] + 273), P=(res["steamPressureMS"] * 0.0980665))
		res["steamEnthalpy"] = steamEnthalpy.h
		fwEnthalpy = IAPWS97(T=(res["FWFinalTemp"] + 273), P=(res["FWFinalPress"] * 0.0980665))
		res["fwEnthalpy"] = fwEnthalpy.h
		hrhEnthalpy = IAPWS97(T=(res["hrhTemp"] + 273), P=(res["hrhPress"] * 0.0980665))
		res["hrhEnthalpy"] = hrhEnthalpy.h
		crhEnthalpy = IAPWS97(T=(res["crhTemp"] + 273), P=(res["crhPress"] * 0.0980665))
		res["crhEnthalpy"] = crhEnthalpy.h

		res["crhFlow"] = (0.8744 - 0.0066 * ((res["load"] - 90.0)) / 30.0) * res["steamFlowMS"]

		res["turbineHeatRate"] = ((res["steamFlowMS"] * (res["steamEnthalpy"] - res["fwEnthalpy"])) 
									+ ((res["crhFlow"] + res["reheatSprayFlow"]) * res["hrhEnthalpy"]) 
									- (res["crhEnthalpy"]  * res["crhFlow"]) 
									- (res["hrhEnthalpy"] * res["reheatSprayFlow"])) / (res["load"] * 4.1868)

		
		# print (json.dumps(res, indent=4))

		return res

	elif str(res["category"]) == "DBPower":
		#dbp thr formula
		steamEnthalpy = IAPWS97(T=(res["steamTempMS"] + 273), P=(res["steamPressureMS"] * 0.0980665))
		res["steamEnthalpy"] = steamEnthalpy.h/4.1868 

		fwEnthalpy = IAPWS97(T=(res["FWFinalTemp"] + 273), P=(res["FWFinalPress"] * 0.0980665))
		res["fwEnthalpy"] = fwEnthalpy.h/4.1868 

		hrhEnthalpy = IAPWS97(T=(res["hrhTemp"] + 273), P=(res["hrhPress"] * 0.0980665))
		res["hrhEnthalpy"] = hrhEnthalpy.h/4.1868 

		crhEnthalpy = IAPWS97(T=(res["crhTemp"] + 273), P=(res["crhPress"] * 0.0980665))
		res["crhEnthalpy"] = crhEnthalpy.h/4.1868 

		shEnthalpy = IAPWS97(T=(res["shTemp"] + 273), P=(res["shPress"] * 0.0980665))
		res["shEnthalpy"] = shEnthalpy.h/4.1868 
		fwOLEnthalpy = IAPWS97(T=(res["FWFinalTemp"] + 273), P=(res["FWFinalPress"] * 0.0980665))
		res["FW_O/L_FromHPH-6AEnthalpy"]= fwOLEnthalpy.h/4.1868 

		fwILEnthalpy = IAPWS97(T=(res["fwILTemp"] + 273), P=(res["fwILPress"] * 0.0980665))
		res["FW_I/L_ToHPH-6Enthalpy"]=fwILEnthalpy.h/4.1868 

		ExtractionSteamEnthalpyToHPH = IAPWS97(T=(res["ExtractionSteamTemp"] + 273), P=(res["ExtractionSteamPress"] * 0.0980665))
		res["ExtractionSteamEnthalpyToHPH-6"]=ExtractionSteamEnthalpyToHPH.h/4.1868 

		Drip6Enthalpy = IAPWS97(T=(res["Drip6Temp"] + 273), P=(res["ExtractionSteamPress"] * 0.0980665))
		res["Drip6Enthalpy"]=Drip6Enthalpy.h/4.1868 

		res["steamFlowMS"]= res["EcoInletFeedWaterFlow"]+res["SuperheaterAttempFlow"]
		res["TotalExtractionFlowTo(HPH6A+6B)"]= ((res["EcoInletFeedWaterFlow"]+res["SuperheaterAttempFlow"])*(res["FW_O/L_FromHPH-6AEnthalpy"]-res["FW_I/L_ToHPH-6Enthalpy"]))/(res["ExtractionSteamEnthalpyToHPH-6"]-res["Drip6Enthalpy"])
		res["ColdReheatSteamFlow"] =res["steamFlowMS"]-res["TotalExtractionFlowTo(HPH6A+6B)"]-10.3
		res["hrhFlow"]=res["steamFlowMS"]-res["TotalExtractionFlowTo(HPH6A+6B)"]-10.3+res["reheatSprayFlow"]
		res["thrEntSum1"] = res["steamFlowMS"] *(res["steamEnthalpy"]-res["fwEnthalpy"])
		res["thrEntSum2"]= res["hrhFlow"] *(res["hrhEnthalpy"]-res["crhEnthalpy"])
		res["thrEntSum3"]=res["SuperheaterAttempFlow"]*(res["fwEnthalpy"]-res["shEnthalpy"])
		res["turbineHeatRate"]= (res["thrEntSum1"]+res["thrEntSum2"]+res["thrEntSum3"])/res["load"]

		return res 

	else:
		steam1 = IAPWS97(T=(res["steamTempMS"] + 273), P=(res["steamPressureMS"] * 0.0980665))
		steam2 = IAPWS97(T=(res["FWFinalTemp"] + 273), P=(res["FWFinalPress"] * 0.0980665))
		enthalpyMS, enthalpyFW = steam1.h / 4.18, steam2.h / 4.18
		# print "ENthalpy : ", enthalpyMS, enthalpyFW, res["steamFlowMS"], (res["steamFlowMS"] * (enthalpyMS - enthalpyFW)) / res["load"], res["FWFinalTemp"] + 273, res["FWFinalPress"]
		return {"turbineHeatRate" : (res["steamFlowMS"] * (enthalpyMS - enthalpyFW)) / res["load"]}
		

	
# Function for plant HRT
@app.route('/efficiency/phr', methods=['POST'])
def PHRCalculation():

	res = request.json
	# print ("phr")
	print (res)
	ble, thr = 0.0, 0.0 
	
	if (len(res["boilerEfficiency"]) != len(res["boilerSteamFlow"])) or (len(res["turbineHeatRate"]) != len(res["turbineSteamFlow"])):
		return json.dumps({"error" : "bad request"}), 400

	if (sum(res["boilerSteamFlow"]) == 0) or (sum(res["turbineSteamFlow"]) == 0):
		for i in range(len(res["boilerEfficiency"])):
			ble = ble + (res["boilerEfficiency"][i] * res["boilerSteamFlow"][i])
		ble /= sum(res["boilerSteamFlow"])
		return {"plantHeatRate" : 0.0, "averageBoilerEfficiency":ble}

	ble, thr = 0.0, 0.0 
	for i in range(len(res["boilerEfficiency"])):
		ble = ble + (res["boilerEfficiency"][i] * res["boilerSteamFlow"][i])
	ble /= sum(res["boilerSteamFlow"])

	print ("ble",ble)

	for i in range(len(res["turbineHeatRate"])):
		thr = thr + (res["turbineHeatRate"][i] * res["turbineSteamFlow"][i])
	thr /= sum(res["turbineSteamFlow"])
	print ("thr",thr)
	plantHeatRate = (thr * 100.0) / ble
	averageBoilerEfficiency = ble

	res["plantHeatRate"] = plantHeatRate
	res["averageBoilerEfficiency"] = averageBoilerEfficiency
	print("plantHeatRate" , (thr * 100.0) / ble)
	
	return res

@app.route('/efficiency/fuelValidate', methods=['POST'])
def validate_json():
	res = request.json
	print(res)
	if res["type"]=="proximate":
		for i in ["coalFC", "coalVM", "coalAsh", "coalMoist"]:
			if (i not in res):

				print ("error: " + str(i) + " missing or '0' found")

				return json.dumps({"error" : str(i) + " missing or '0' found"}), 400

		total_sum = float(res["coalFC"]) + float(res["coalVM"]) +float( res["coalAsh"]) + float(res["coalMoist"])
	   
	elif res["type"]=="ultimate":
		for i in ["carbon", "nitrogen", "hydrogen", "oxygen","coalAsh","coalSulphur","coalMoist"]:
			if (i not in res):
				print ("error: " + str(i) + " missing or '0' found")
				return json.dumps({"error" : str(i) + " missing or '0' found"}), 400

		total_sum = float(res["carbon"]) +float(res["nitrogen"]) + float(res["hydrogen"]) + float(res["oxygen"]) +float(res["coalAsh"]) +float(res["coalSulphur"]) + float(res["coalMoist"])
		

	if total_sum < 95 or total_sum > 105:
		return jsonify({"valid" : False})
	else:
		return jsonify({"valid" : True})

@app.route('/efficiency/blendValidate', methods=['POST'])
def validate_blend():
	res= request.json

	total_percentage = sum(fuel_input["value"] for fuel_input in res["fuelInputs"])
	# print "total_percentage",total_percentage
	if total_percentage > 100:
		return jsonify({"valid": False})
	else:
		return jsonify({"valid": True})


# Function for plant HRT
@app.route('/efficiency/test', methods=['POST'])
def test():
	return {"status":"passed."}, 200


boilerEfficiency_index = {"type1" : boilerEfficiencyType1, 
						"type2" : boilerEfficiencyType2, 
						"type3" : boilerEfficiencyType3, 
						"type4" : boilerEfficiencyType4, 
						"type5" : boilerEfficiencyType5, 
						"type6" : boilerEfficiencyType6, 
						"type7" : boilerEfficiencyType7, 
						"type8" : boilerEfficiencyType8, 
						"type9" : boilerEfficiencyType9,
						"type10" : boilerEfficiencyType10,
						"type11" : boilerEfficiencyType11,
						"type12" : boilerEfficiencyType12,
						"type13" : boilerEfficiencyType13,
						"type15" : boilerEfficiencyType15,
						"type18" : boilerEfficiencyType18
						}
					

# {"before_start_time":1701432000000,"before_end_time":1701777600000,"after_start_time":1701950400000,"after_end_time":1702209600000,"random":"JmSLtGnwZc",
	#   "type":"waterfall","unitid":"61c1818371c20d4a206a2e35","systemName":"Afbc 3"}

def fetch_efficiency_mapping(unitId):
	mapping_file_url = config["api"]["meta"]+'/boilerStressProfiles?filter={"where":{"type":"efficiencyMapping", "unitsId":"'+str(unitId)+'"}}'
	print (mapping_file_url)
	response = requests.get(mapping_file_url)
	if response.status_code == 200:
		return response.json()
	else:
		print (response.status_code)
		print ("\n\nUnable to fetch efficiency mapping for this unit, " + str(unitId))
		return []


def get_data_epoch(tagList, startTime, endTime):
	qr = ts.timeseriesquery()
	qr.addMetrics(tagList)
	qr.chooseTimeType("absolute",{"start_absolute":str(startTime), "end_absolute":str(endTime)})
	# qr.addAggregators([{"name":"avg", "sampling_value":1,"sampling_unit":"hours"}])
	qr.submitQuery()
	qr.formatResultAsDF()
	if (len(qr.resultset["results"]) > 0):
		values = qr.resultset["results"][0]["data"]
		# print values.shape
		return values
	else:
		print ("no datapoints found in production kairos")
		return pd.DataFrame()



def get_heatrates(unitId):
	heatrate_url = config["api"]["meta"]+'/units/'+str(unitId)+'/heatrates'
	response = requests.get(heatrate_url)
	if response.status_code == 200:
		return response.json()
	else:
		print (response.status_code)
		print ("\n\nUnable to fetch efficiency mapping for this unit, " + str(unitId))
		return []

def get_forms(unitId):
	savings_form_url = config["api"]["meta"]+'/units/'+str(unitId)+'/forms?filter={"where":{"name":"Savings"}}'
	print (savings_form_url)
	response = requests.get(savings_form_url)
	if response.status_code == 200:
		return response.json()
	else:
		print (response.status_code)
		print ("\n\nUnable to fetch efficiency mapping for this unit, " + str(unitId))
		return []


def getLastValues(taglist,end_absolute=0):
	endTime = int((time.time()*1000) + (5.5*60*60*1000))
	if end_absolute !=0:
		query = {"metrics": [],"start_absolute": 1, "end_absolute":endTime }
	else:
		query = {"metrics": [],"start_absolute":1,"end_absolute":endTime}
	for tag in taglist:
		query["metrics"].append({"name": tag,"order":"desc","limit":1})
	try:
		res = requests.post(config['api']['query'],json=query).json()
		df = pd.DataFrame([{"time":res["queries"][0]["results"][0]["values"][0][0]}])
		for tag in res["queries"]:
			try:
				if df.iloc[0,0] <  tag["results"][0]["values"][0][0]:
					df.iloc[0,0] =  tag["results"][0]["values"][0][0]
				df.loc[0,tag["results"][0]["name"]] = tag["results"][0]["values"][0][1]
			except:
				pass
	
	except Exception as e:
		#print(e)
		return pd.DataFrame()
	return df

def get_single_day_data(tag, startTime, endTime):
	df = getLastValues([tag])
	if df.empty:
		return "-"
	if startTime <= df.loc[df.shape[0]-1, "time"] <= endTime:
		return round(df.loc[df.shape[0]-1, tag], 2)
	else:
		return "-"
  
	
def get_single_day_data_2(tag, startTime, endTime):
	endTime = startTime + (6*3600*1000)
	startTime = startTime - (6*3600*1000)
	print (endTime, startTime, "single dat data")
	qr = ts.timeseriesquery()
	qr.addMetrics([tag])
	qr.chooseTimeType("absolute",{"start_absolute":str(startTime), "end_absolute":str(endTime)})
	# qr.addAggregators([{"name":"avg", "sampling_value":1,"sampling_unit":"hours"}])
	qr.submitQuery()
	# print (qr.resultset)
	try:
		qr.formatResultAsDF()
		df = qr.resultset["results"][0]["data"]
		# print (df.loc[df.shape[0]-1])
		return df.loc[df.shape[0]-1, tag]
	except Exception as e:
		print ("error in getting kairos data", e)
		return "-"
	
def get_month_start_time_in_epoch():
	current_date = datetime.now()
	# print (current_date)
	start_of_month = current_date.replace(day=1, minute=0, hour=0, second=0)
	# print (start_of_month.timestamp())
	epoch_milliseconds = int(((int(start_of_month.timestamp() ))* 1000) - (5.5*3600*1000))
	return (epoch_milliseconds)

def get_year_start_time_in_epoch():
	current_date = datetime.now()
	start_of_year = current_date.replace(month=1, day=1)
	epoch_milliseconds = int((start_of_year.timestamp() / 1000 )* 1000)
	return (epoch_milliseconds)

def get_monthly_simple_cumulative_data(tag, startTime, endTime):
	startTime = get_month_start_time_in_epoch()
	qr = ts.timeseriesquery()
	qr.addMetrics([tag])
	print (startTime, endTime, "for simple monthly")
	qr.chooseTimeType("absolute",{"start_absolute":str(startTime), "end_absolute":str(endTime)})
	qr.addAggregators([{"name":"sum", "sampling_value":2,"sampling_unit":"years"}])
	qr.submitQuery()
	try:
		qr.formatResultAsDF()
		df = qr.resultset["results"][0]["data"]
		print (df)
		return round(df.loc[df.shape[0]-1, tag], 2)
	except Exception as e:
		print ("error in getting kairos data", e)
		return "-"

CALENDER_CONFIG = {"January":1, "February":2, "March":3, "April":4, "May":5, "June":6, "July":7, "August":8, "September":9, 
				   "October":10, "November":11, "December":12}
	

def get_current_month_and_year():
	current_date = datetime.now()
	current_month = current_date.month
	current_year = current_date.year
	return current_month, current_year

def date_to_epoch_milliseconds(year, month, day):
	given_date = datetime(year, month, day)
	# print (given_date.timestamp(), "^^^^^^^^^^^^^^^^^")
	epoch_milliseconds = int(given_date.timestamp() * 1000)
	return epoch_milliseconds

def get_yearly_simple_cumulative_data(tag, startTime, endTime, calender_year):

	current_month, current_year = get_current_month_and_year()
	# print (current_month, current_year)
	if current_month < CALENDER_CONFIG[calender_year[0]]:
		year = current_year - 1
	else:
		year = current_year
	startTime = int(date_to_epoch_milliseconds(year, CALENDER_CONFIG[calender_year[0]], 1) - (5.5*3600*1000))
	# print (endTime, startTime, "$$$$$$$$$$$$$")
	print (startTime, endTime, "for simple yearly")
	qr = ts.timeseriesquery()
	qr.addMetrics([tag])
	qr.chooseTimeType("absolute",{"start_absolute":str(startTime), "end_absolute":str(endTime)})
	qr.addAggregators([{"name":"sum", "sampling_value":2,"sampling_unit":"years"}])
	# print (qr.query)
	qr.submitQuery()
	# print (qr.resultset)
	try:
		qr.formatResultAsDF()
		df = qr.resultset["results"][0]["data"]
		# print (df)
		# print (df.loc[df.shape[0]-1])
		return round(df.loc[df.shape[0]-1, tag], 2)
	except Exception as e:
		print ("error in getting kairos data", e)
		return "-"

	
def get_simple_cumulative(simple_cumulative_tags, startTime, endTime, calender_year, measure_unit_dict):
	result_simple_cumulative = {}
	for sc_tag in simple_cumulative_tags:
		result_simple_cumulative[sc_tag] = {}
		if endTime - startTime > (24*60*60*1000):
			result_simple_cumulative[sc_tag]["day"] = "-"

		else:
			result_simple_cumulative[sc_tag]["day"] = get_single_day_data(sc_tag, startTime, endTime)
		
		result_simple_cumulative[sc_tag]["mtd"] = get_monthly_simple_cumulative_data(sc_tag, startTime,endTime,)
		result_simple_cumulative[sc_tag]["ytd"] = get_yearly_simple_cumulative_data(sc_tag, startTime, endTime, calender_year)
		try:
			result_simple_cumulative[sc_tag]["measureUnit"] = measure_unit_dict[sc_tag]
		except:
			print ("meta absent for this tag : ", str(sc_tag), "hence yarstick report UI errors")
			result_simple_cumulative[sc_tag]["measureUnit"] = "-"
	return result_simple_cumulative

def get_duration_in_months(startTime, endTime):
	dt_object = datetime.utcfromtimestamp(startTime / 1000)
	month_1 = dt_object.month
	year_1 = dt_object.year
	dt_object = datetime.utcfromtimestamp(endTime / 1000)
	month_2 = dt_object.month
	year_2 = dt_object.year
	return (int(month_1), int(year_1), int(month_2), int(year_2))

def get_end_date(month_number):
	last_day = calendar.monthrange(2022, month_number)[1]
	end_date = f"2022-{month_number:02d}-{last_day:02d}"
	return int(end_date[-2:])

def calculate_cumulative_sum(data, startDate):
	cumulative_sum = 0
	result = {}

	today = datetime.today()
	for date_str, value in data.items():
		date = datetime.strptime(date_str, "%Y-%m-%d")
		days_difference = (date - datetime.strptime(startDate, "%Y-%m-%d")).days + 1

		cumulative_sum += value * days_difference
		result[date_str] = cumulative_sum

	return result

def get_monthly_running_cumulative_data(tag, startTime, endTime, calender_year):
	print ("from monthly running cums")
	month_1, year_1, month_2, year_2 = get_duration_in_months(startTime, endTime)
	endDate = get_end_date(month_2)
	startTime = int(int(datetime(year_1, month_1, 1).timestamp()) * 1000 - (5.5*3600*1000))
	endTime_sub = int(datetime(year_2, month_2, endDate).timestamp()) * 1000
	# print (startTime, endTime_sub, "&5"*40)
	qr = ts.timeseriesquery()
	qr.addMetrics([tag])
	qr.chooseTimeType("absolute",{"start_absolute":str(startTime), "end_absolute":str(endTime_sub)})
	# qr.addAggregators([{"name":"sum", "sampling_value":2,"sampling_unit":"years"}])
	qr.submitQuery()
	# print (qr.resultset)
	try:
		qr.formatResultAsDF()
		df = qr.resultset["results"][0]["data"]
		print (df)
		if df.empty:
			return "-"
		else:
			df["time"] = df["time"] + (5.5*60*60*1000)
			df["Date"] = pd.to_datetime(df["time"], unit='ms').dt.strftime('%Y-%m-%d')
			# df = df.sort_values(by='Date')
			input_data  = df.set_index("Date")[tag].to_dict()
			print (input_data, tag)
			running_cumsum = 0.0
			for k,v in input_data.items():
				date = datetime.strptime(k, "%Y-%m-%d")

				formatted_date = datetime.strptime(datetime.fromtimestamp(endTime / 1000.0).strftime("%Y-%m-%d"), "%Y-%m-%d")
				# today_date = datetime.strptime(datetime.now().strftime("%Y-%m-%d"), "%Y-%m-%d")
				# today_date = datetime.strptime("2023-12-13", "%Y-%m-%d")
				# print (formatted_date, date)
				diff = (formatted_date - date).days
				# print (diff, diff*v)
				running_cumsum = running_cumsum + diff*v
			return round(running_cumsum,2)

	except Exception as e:
		print ("error in getting kairos data", e)
		return "-"


def get_yearly_running_cumulative_data(tag,  startTime, endTime, calender_year):
	print ("from yearly running cums")
	current_month, current_year = get_current_month_and_year()
	print (current_month, current_year)
	if current_month < CALENDER_CONFIG[calender_year[0]]:
		year = current_year - 1
	else:
		year = current_year
	startTime = int(date_to_epoch_milliseconds(year, CALENDER_CONFIG[calender_year[0]], 1) - (5.5*3600*1000))
	print (endTime, startTime)
	qr = ts.timeseriesquery()
	qr.addMetrics([tag])
	qr.chooseTimeType("absolute",{"start_absolute":str(startTime), "end_absolute":str(endTime)})
	# qr.addAggregators([{"name":"sum", "sampling_value":2,"sampling_unit":"years"}])
	qr.submitQuery()
	print (qr.resultset)
	try:
		qr.formatResultAsDF()
		df = qr.resultset["results"][0]["data"]
		if df.empty:
			return "-"
		else:
			df["time"] = df["time"] + (5.5*60*60*1000)
			df["Date"] = pd.to_datetime(df["time"], unit='ms').dt.strftime('%Y-%m-%d')
			# df = df.sort_values(by='Date')
			input_data  = df.set_index("Date")[tag].to_dict()
			print (input_data, tag)
			running_cumsum = 0.0
			for k,v in input_data.items():
				date = datetime.strptime(k, "%Y-%m-%d")

				formatted_date = datetime.strptime(datetime.fromtimestamp(endTime / 1000.0).strftime("%Y-%m-%d"), "%Y-%m-%d")
				# today_date = datetime.strptime(datetime.now().strftime("%Y-%m-%d"), "%Y-%m-%d")
				# today_date = datetime.strptime("2023-12-13", "%Y-%m-%d")
				print (formatted_date, date)
				diff = (formatted_date - date).days
				print (diff, diff*v)
				running_cumsum = running_cumsum + diff*v
			return round(running_cumsum, 2)

	except Exception as e:
		print ("error in getting kairos data", e)
		return "-"


def get_running_cumulative(running_cumulative_tags, startTime, endTime, calender_year, measure_unit_dict):
	result_running_cumulative = {}
	for sc_tag in running_cumulative_tags:
		result_running_cumulative[sc_tag] = {}
		if endTime - startTime > (24*60*60*1000):
			result_running_cumulative[sc_tag]["day"] = "-"

		else:
			result_running_cumulative[sc_tag]["day"] = get_single_day_data(sc_tag, startTime, endTime)
		
		result_running_cumulative[sc_tag]["mtd"] = get_monthly_running_cumulative_data(sc_tag, startTime, endTime, calender_year)
		result_running_cumulative[sc_tag]["ytd"] = get_yearly_running_cumulative_data(sc_tag, startTime, endTime, calender_year)
		try:
			result_running_cumulative[sc_tag]["measureUnit"] = measure_unit_dict[sc_tag]
		except:
			print ("meta absent for this tag : ", str(sc_tag), "hence yarstick report UI errors")
			result_running_cumulative[sc_tag]["measureUnit"] = "-"
	return result_running_cumulative

def handle_limits_of_tagmeta(tagMeta):
	if isinstance(tagMeta["limRangeHi"], (int, float)) == False:
		tagMeta["limRangeHi"] = 0.0
	if isinstance(tagMeta["limHiHi"], (int, float)) == False:
		tagMeta["limHiHi"] = 0.0
	if isinstance(tagMeta["limHi"], (int, float)) == False:
		tagMeta["limHi"] = 0.0
	if isinstance(tagMeta["limRangeLo"], (int, float)) == False:
		tagMeta["limRangeLo"] = 0.0
	return tagMeta

def get_gauge_calcs(tags, startTime, endTime):
	print ("in dial gauge \n\n")
	def getcsum(tag, unit):
		# url = "https://pulse.thermaxglobal.com/exactdata/api/v1/datapoints/query"
		url = config["api"]["query"]
		d = {
			"metrics": [
				{
				"tags": {},
				"name": "",
				"aggregators": [
					{
					"name": "avg",
					"sampling": {
						"value": "1",
						"unit": unit
					}
					}
				]
				}
			],
			"plugins": [],
			"cache_time": 0,
			"start_absolute": startTime,
			"end_absolute": endTime
			}
		finalDF = pd.DataFrame()
		
		d['metrics'][0]['name'] = tag
		res = requests.post(url=url, json=d,auth=('AAA', 'AAAA'))
		try:
			values = json.loads(res.content)
			df = pd.DataFrame(values["queries"][0]["results"][0]['values'], columns=['time', 'values'])
		except Exception as e:
			print (e, "error in fecthign data for guage tags")
			df = pd.DataFrame()
	
		finalDF = pd.concat([finalDF, df], axis=1)
		try:
			finalDF = finalDF.loc[:, ~finalDF.columns.duplicated()]
			finalDF.dropna(subset=['time'], inplace=True)
			csum = finalDF['values'].cumsum().iloc[-1]
		except Exception as e:
			print (e, "due to kairos issues, calcs are going wrong here")
			csum = 0.0

		print (csum, "come one please ")
		return csum

	result = {}
	for tag in tags:
		tagmetaurl = config["api"]["meta"] +'/tagmeta?filter={"where":{"dataTagId":"'+tag+'"}}'
		response = requests.get(tagmetaurl)
		if response.status_code == 200:
			try:
				tagMeta = json.loads(response.content)[0]
			except:
				print ("this : ", tag , " tagmeta is empty hence error in report yardstick ui")
				tagMeta = {}
			try:
				unit = tagMeta["measureUnit"]  
			except:
				unit = "-"
			print (unit)
			if unit == 'Tph' or unit == 'TPH' or '/hour' in unit:
				cs = getcsum(tag, 'hours')
				diff = (endTime - startTime)/(3600000*24)
				print (diff, "%%%%%%%")
				if "limRangeHi" in tagMeta and "limHiHi" in tagMeta and "limHi" in tagMeta and "limRangeLo" in tagMeta:
					tagMeta = handle_limits_of_tagmeta(tagMeta)
					rslt = {"cum_sum" : cs, "measureUnit":tagMeta["measureUnit"], "limRangeHi" : tagMeta["limRangeHi"]*diff, "limHiHi" : tagMeta["limHiHi"]*diff, "limHi" : tagMeta["limHi"]*diff, "limRangeLo":tagMeta["limRangeLo"]*diff}
				else:
					rslt = {"cum_sum" : cs, "measureUnit":tagMeta["measureUnit"],"limRangeHi" : 0.0, "limHiHi" : 0.0, "limHi" : 0.0, "limRangeLo":0.0}
				result[tag] = rslt     
			elif '/min' in unit:
				cs = getcsum(tag, 'minutes')
				diff = (endTime - startTime)/60000
				if "limRangeHi" in tagMeta and "limHiHi" in tagMeta and "limHi" in tagMeta and "limRangeLo" in tagMeta:
					tagMeta = handle_limits_of_tagmeta(tagMeta)
					rslt = {"cum_sum" : cs, "measureUnit":tagMeta["measureUnit"],"limRangeHi" : tagMeta["limRangeHi"]*diff, "limHiHi" : tagMeta["limHiHi"]*diff, "limHi" : tagMeta["limHi"]*diff, "limRangeLo":tagMeta["limRangeLo"]*diff}
				else:
					rslt = {"cum_sum" : cs, "measureUnit":tagMeta["measureUnit"],"limRangeHi" : 0.0, "limHiHi" : 0.0, "limHi" : 0.0, "limRangeLo":0.0}
				result[tag] = rslt
			elif unit == 'MW' or unit == 'mw' or unit == 'KW' or unit == 'kw':
				cs = getcsum(tag, 'hours')
				diff = (endTime - startTime)/(3600000*24)
				print (diff, cs, "%%%%%%%")
				print("added 24hrs logical modification")
				if "limRangeHi" in tagMeta and "limHiHi" in tagMeta and "limHi" in tagMeta and "limRangeLo" in tagMeta:
					tagMeta = handle_limits_of_tagmeta(tagMeta)
					rslt = {"cum_sum" : cs, "measureUnit":tagMeta["measureUnit"], "limRangeHi" : tagMeta["limRangeHi"]*diff, "limHiHi" : tagMeta["limHiHi"]*diff, "limHi" : tagMeta["limHi"]*diff, "limRangeLo":tagMeta["limRangeLo"]*diff}
				else:
					rslt = {"cum_sum" : cs, "measureUnit":tagMeta["measureUnit"],"limRangeHi" : 0.0, "limHiHi" : 0.0, "limHi" : 0.0, "limRangeLo":0.0}
				result[tag] = rslt 
			else:
				"""
				This else part is same as the above elif part coz the definition of the dial gauge has been changed. Logically it makes sense to have only one else part but following the principle of 'dont touch what works', a consious decision of making another else part has been made by the developer. Thats all. 
				"""
				cs = getcsum(tag, 'minutes')
				diff = (endTime - startTime)/60000
				if "limRangeHi" in tagMeta and "limHiHi" in tagMeta and "limHi" in tagMeta and "limRangeLo" in tagMeta:
					tagMeta = handle_limits_of_tagmeta(tagMeta)
					rslt = {"cum_sum" : cs, "measureUnit":tagMeta["measureUnit"],"limRangeHi" : tagMeta["limRangeHi"]*diff, "limHiHi" : tagMeta["limHiHi"]*diff, "limHi" : tagMeta["limHi"]*diff, "limRangeLo":tagMeta["limRangeLo"]*diff}
				else:
					rslt = {"cum_sum" : cs, "measureUnit":tagMeta["measureUnit"],"limRangeHi" : 0.0, "limHiHi" : 0.0, "limHi" : 0.0, "limRangeLo":0.0} 
				result[tag] = rslt
		else:
			print (response.status_code)
			print ("error in getting meta")
	return result


def get_measure_unit(tags):
	url = config["api"]["meta"] + '/tagmeta?filter={"where":{"dataTagId":{"inq":'+json.dumps(tags)+'}}, "fields":["dataTagId", "measureUnit"]}'
	res = requests.get(url)
	if res.status_code == 200:
		response = json.loads(res.content)
		result = {}
		for meta in response:
			result[meta["dataTagId"]] = meta["measureUnit"]
		return result

	else:
		print ("Some error in getting measureUnit from tagmeta for tags: ", res.status_code)
		return 

def create_tag_description_dict(savings_forms):
	tag_description_dict = {}
	for field in savings_forms[0]["fields"]:
		if (field["level"] == 1) and (field["calcType"] == "summation"):
			tag_description_dict[field["dataTagId"]] = field["display"]
		elif (field["level"] == 2) and (field["calcType"] == "cumulation"):
			tag_description_dict[(field["display"].split("(")[0]).strip()] = (field["display"].split("(")[0]).strip()
	return tag_description_dict


@app.route('/efficiency/powerYardstickReportCalcs', methods=['POST'])
def yardstick():
	requestBody = request.json
	print('requestBody',requestBody)
	unitId = requestBody["unitId"]
	endTime = requestBody["endTime"]
	startTime = requestBody["startTime"]

	heat_rates_object = get_heatrates(unitId)
	try:
		savings_forms_object = get_forms(unitId)
	except Exception as e:
		print (e, " error in gettign savings forms for this unit: ", unitId)
		savings_forms_object = []

	# savings_forms_object = []
	try:
		tag_description_dict =  create_tag_description_dict(savings_forms_object)
	except Exception as e:
		print (e, " error in gettign savings forms for this unit: ", unitId)
		tag_description_dict = {}
	

	try:
		savings_tags = [field["dataTagId"] for field in savings_forms_object[0]["fields"]]
	except Exception as e:
		print (e, " error in gettign savings forms for this unit: ", unitId)
		savings_tags = []

	dial_guage_graphs_tags = heat_rates_object[0]["performanceDict"]["tags"]
	calender_year = heat_rates_object[0]["calenderYearDict"]["tags"]
	measure_unit_dict = get_measure_unit(dial_guage_graphs_tags+savings_tags)
	# print (savings_tags, dial_guage_graphs_tags, calender_year)
	try:
		simple_cumulative_tags = [field["dataTagId"]  for field in savings_forms_object[0]["fields"] if field["calcType"] == "summation"]
		running_cumulative_tags = [field["dataTagId"]  for field in savings_forms_object[0]["fields"] if field["calcType"] == "cumulation"]
		simple_cumulative = get_simple_cumulative(simple_cumulative_tags, startTime, endTime, calender_year, measure_unit_dict)
		running_cumulative = get_running_cumulative(running_cumulative_tags, startTime, endTime, calender_year, measure_unit_dict)
	except Exception as e:
		print (e, " error in gettign savings forms for this unit: ", unitId)
		simple_cumulative = {}
		running_cumulative = {}



	# print (simple_cumulative, running_cumulative)
	# print (zz)

	gauge_result = get_gauge_calcs(dial_guage_graphs_tags, startTime, endTime)
	result = {}
	try:
		result["table"] = {}
		if savings_forms_object:
			for field in savings_forms_object[0]["fields"]:
				# print (field["level"], field["calcType"], field["dataTagId"])
				if (field["level"] == 1) and (field["calcType"] == "summation"):
					for k,v in simple_cumulative.items():
						if field["dataTagId"] == k:
							result["table"][k] = v
				# print (json.dumps(result, indent=4), "100")
				# print (field)
				if (field["level"] == 2):
					required_tag_desc = (field["display"].split("(")[0]).strip()
					# print (required_tag_desc)
					for k,v in simple_cumulative.items():
						# print (k, field["dataTagId"], "summation")
						if field["dataTagId"] == k:
							# print (required_tag_desc, result["table"].keys()) 
							if required_tag_desc not in result["table"].keys():
								result["table"][required_tag_desc] = v
								# print (json.dumps(result, indent=4)) 
							else:
								# print (result["table"][required_tag_desc], v)
								for k2, v2 in v.items():
									if k2 != "measureUnit":
										try:
											if (result["table"][required_tag_desc][k2]) == "-":
												print(f"Replacing '-' in result for {k2} with 0")
												(result["table"][required_tag_desc][k2])= 0
											if v2 == '-':
												print(f"Replacing '-' in v2 for {k2} with 0")
												v2 = 0
											result["table"][required_tag_desc][k2] = float(result["table"][required_tag_desc][k2]) + float(v2)
											if result["table"][required_tag_desc][k2] ==0:
												result["table"][required_tag_desc][k2] ="-"
										except Exception as e:
											print (e, " error in adding cumulaive and summation part")
											result["table"][required_tag_desc][k2] = "-"
					for k,v in running_cumulative.items():
						# print (k, field["dataTagId"], "cumulative")
						# print (json.dumps(result, indent=4), "101")
						if field["dataTagId"] == k:
							# print (required_tag_desc, result["table"].keys()) 
							if required_tag_desc not in result["table"].keys():
								result["table"][required_tag_desc] = v
								# print (json.dumps(result, indent=4), "300") 
							else:
								print (result["table"][required_tag_desc], v)
								# print (json.dumps(result, indent=4), "200")
								for k2, v2 in v.items():
									try:
										if (result["table"][required_tag_desc][k2]) == "-":
												print(f"Replacing '-' in result for {k2} with 0")
												(result["table"][required_tag_desc][k2])= 0
										if v2 == '-':
											print(f"Replacing '-' in v2 for {k2} with 0")
											v2 = 0
										result["table"][required_tag_desc][k2] = float(result["table"][required_tag_desc][k2]) + float(v2)
										if result["table"][required_tag_desc][k2] ==0:
											result["table"][required_tag_desc][k2] ="-"
									except Exception as e:
										print (e, " error in adding cumulaive and summation part")
										result["table"][required_tag_desc][k2] = "-"
	except Exception as e:
		print (e, "   --> savings form not configured as per DCM / bataan. Please update the savings form in DCM format please. \n\n")
		result["table"] = {}	


	for k,v in result["table"].items():
		# print (tag_description_dict)
		result["table"][k]["description"] = tag_description_dict[k]
		if isinstance(v['ytd'], (int, float)):
			v['ytd'] = round(v['ytd'], 2)
			
	#below is to ensure page doesnt break even if no forms are made or some config issues with savigns forms object
	if bool(simple_cumulative) == False and bool(running_cumulative) == False:
		result["table"] = {
		"data_tag_id": {
			"day": "-",
			"mtd": "-",
			"ytd": "-",
		  "measureUnit": "-","description":"Savings"
		}}

	
	result["gauge"] = {}
	for k,v in gauge_result.items():
		result["gauge"][k] = v
	if "Cost of Operation Saving" in result["table"]:
		del result["table"]["Cost of Operation Saving"]
	return json.dumps(result, cls=NpEncoder)


def jsw_specific_thr_dev_calculations(requestBody):
	# print (json.dumps(requestBody, indent=4))

	requestBody["gross_heat_rate"] = requestBody["turbineHeatRate"] / (requestBody["boilerEfficiency"] / 100.0)

	requestBody["thr_dev_due_to_load"] = (((1728.4 + 54360.0 / requestBody["load"]) - (1728.4+ 54360.0 / 300.078)) / ((88.77 - 0.011 * (requestBody["load"] - 300.078)) / 100.0)) / (requestBody["boilerEfficiency"] / 100.0)

	requestBody["design_main_steam_press"] = 0.0
	if requestBody["load"] < 240.0:
		requestBody["design_main_steam_press"] = (0.0439 * requestBody["load"]) +  5.9673
	else:
		requestBody["design_main_steam_press"] = 16.67
	
	
	requestBody["thr_dev_due_to_msp"] = 0.0
	if requestBody["load"] < 5.0:
		requestBody["thr_dev_due_to_msp"] = 0.0
	elif requestBody["load"] >= 240.0:
		requestBody["thr_dev_due_to_msp"] = requestBody["gross_heat_rate"]  * (((-0.6394 * (requestBody["steamPressureMS"])) + 10.654) / 100.0)
	else:
		if requestBody["design_main_steam_press"] < requestBody["steamPressureMS"]:
			requestBody["thr_dev_due_to_msp"] = 0.0
		else:
			requestBody["thr_dev_due_to_msp"] = (requestBody["design_main_steam_press"] - requestBody["steamPressureMS"]) * 12.8



	requestBody["thr_dev_due_to_mst"]  = requestBody["gross_heat_rate"] * (((-0.0278*requestBody["steamTempMS"]) + 14.962) / 100.0) 
	requestBody["thr_dev_due_to_ipt_il_tmp"]  = requestBody["gross_heat_rate"] * (((-0.0247*requestBody["IptInletSteamTemp"]) + 13.303) / 100.0)

	requestBody["thr_dev_due_to_cond_vac"]  = requestBody["gross_heat_rate"] * (((0.654*(requestBody["CondenserVacuum"] +  101.32)) - 6.6122) / 100.0) 


	requestBody["thr_dev_due_to_sh_spray"]  =  requestBody["gross_heat_rate"] * ((0.0398 * (((requestBody["totalShSprayWater"])/requestBody["computedMainSteamFlow_computedFWFlow"]) *100) + 0.0016) / 100.0)

	requestBody["thr_dev_due_to_rh_spray"]  = requestBody["gross_heat_rate"] * (((0.1706* ((requestBody["RhSprayWater"] / requestBody["HrhSteamFlow"]) *100)) + 0.0137) / 100.0)
	requestBody["saturation_temp_of_cond_vac"] = iapws97._TSat_P(P=((requestBody["CondenserVacuum"] +  101.32) / 1000.0)) - 273
	requestBody["thr_dev_due_to_sub_cooling"] = requestBody["gross_heat_rate"] * (((0.1182*(requestBody["saturation_temp_of_cond_vac"] - requestBody["condensateTemp"])) + 0.006) / 100.0)
	

	requestBody["hp_inlet_steam_entropy"] = IAPWS97(T=(requestBody["steamTempMS"] + 273), P=(requestBody["steamPressureMS"])).s
	requestBody["hp_isentropic_expansion_enthalpy"] = IAPWS97(s=(requestBody["hp_inlet_steam_entropy"]), P=((requestBody["HptExhaustPressure"]))).h

	requestBody["hp_turbine_efficiency"] = (requestBody["enthalpyMS"] - requestBody["HptSteamExhaustEnthalpy"]) * 100.0 / (requestBody["enthalpyMS"] - requestBody["hp_isentropic_expansion_enthalpy"])



	# print (requestBody["IptExhaustPressure"], "$"*20)
	requestBody["ipt_exhaust_steam_enthalpy"] = IAPWS97(T=(requestBody["IptExhaustTemp"] + 273), P=(requestBody["IptExhaustPressure"] / 1000.0)).h
	requestBody["ipt_inlet_steam_entropy"] = IAPWS97(T=(requestBody["IptInletSteamTemp"] + 273), P=(requestBody["IptInletSteamPress"])).s
	requestBody["ipt_isentropic_expansion_enthalpy"] = IAPWS97(s=(requestBody["ipt_inlet_steam_entropy"]), P=((requestBody["IptExhaustPressure"] / 1000.0))).h

	requestBody["ip_turbine_efficiency"] = (requestBody["IptInletSteamEnthalpy"] - requestBody["ipt_exhaust_steam_enthalpy"]) * 100.0 / (requestBody["IptInletSteamEnthalpy"] - requestBody["ipt_isentropic_expansion_enthalpy"])

	# print (requestBody["ip_turbine_efficiency"])
	# requestBody["hp_turbine_efficiency"] = 78.77
	# requestBody["ip_turbine_efficiency"] = 89.73

	requestBody["lpt_inlet_enthalpy"] = requestBody["ipt_exhaust_steam_enthalpy"]
	requestBody["dryness_fraction_constant"] = 0.9317
	requestBody["lpt_exhaust_steam_enthalpy"] = IAPWS97(P=((requestBody["CondenserVacuum"] + 101.32) / 1000.0), x=(requestBody["dryness_fraction_constant"])).h
	requestBody["lpt_inlet_steam_entropy"] = IAPWS97(T=(requestBody["IptExhaustTemp"] + 273), P=(requestBody["IptExhaustPressure"] / 1000.0)).s
	requestBody["lpt_isentropic_expansion_enthalpy"] = IAPWS97(s=(requestBody["lpt_inlet_steam_entropy"]), P=((requestBody["CondenserVacuum"] + 101.32) / 1000.0)).h
	requestBody["lp_turbine_efficiency"] = (requestBody["ipt_exhaust_steam_enthalpy"] - requestBody["lpt_exhaust_steam_enthalpy"]) * 100.0 / (requestBody["ipt_exhaust_steam_enthalpy"] - requestBody["lpt_isentropic_expansion_enthalpy"])
	

	requestBody["thr_dev_due_to_hp_turbine_efficiency"] = 0.2 * ((86.96 - requestBody["hp_turbine_efficiency"]) / 100.0) * requestBody["gross_heat_rate"]
	requestBody["thr_dev_due_to_ip_turbine_efficiency"] = 0.2 * ((90.83 - requestBody["ip_turbine_efficiency"]) / 100.0) * requestBody["gross_heat_rate"]

	if requestBody["load"] >= 300.078:
		requestBody["thr_dev_due_to_fw_temp"] = (274.4 - requestBody["FWFinalTemp"]) * 0.8
	else:
		requestBody["thr_dev_due_to_fw_temp"] = (((274.4 + (requestBody["load"] - 300.078) * 0.2475)) - requestBody["FWFinalTemp"]) * 0.8
	requestBody["diff_fw_temp_from_load_and_actual_fw_temp"] = ((0.0892* requestBody["computedMainSteamFlow_computedFWFlow"]) + 193.29) - requestBody["FWFinalTemp"]
	requestBody["thr_dev_due_to_make_up_flow"] = requestBody["gross_heat_rate"] * (-((-0.2326 * ((requestBody["hotwellMakeUpFlow"] / requestBody["computedMainSteamFlow_computedFWFlow"]) *100.0)) + 0.0014) / 100.0)
	requestBody["hr_dev_due_to_dry_flue_gas_loss"] = requestBody["turbineHeatRate"] / ((requestBody["boilerEfficiency"] - (requestBody["LossDueToDryFlueGas"] - 4.82))/ 100.0) - requestBody["turbineHeatRate"] / (requestBody["boilerEfficiency"] / 100.0) + 0.11
	requestBody["hr_dev_due_to_wet_flue_gas_loss"] = requestBody["turbineHeatRate"] / ((requestBody["boilerEfficiency"] - (requestBody["LossDueToH2InFuel"] + requestBody["LossDueToH2OInFuel"] - 4.6))/ 100.0) - requestBody["turbineHeatRate"] / (requestBody["boilerEfficiency"] / 100.0) - 0.06
	requestBody["thr_dev_due_to_UBC_fly_ash"] = requestBody["turbineHeatRate"] / ((requestBody["boilerEfficiency"] - (0.9 * (requestBody["flyAshUnburntCarbon"] - 5) * requestBody["coalAsh"] * 80.77 / requestBody["coalGCV"])) / 100.0) - requestBody["turbineHeatRate"] / (requestBody["boilerEfficiency"] / 100.0) - 5.0
	requestBody["thr_dev_due_to_UBC_bed_ash"] = requestBody["turbineHeatRate"] / ((requestBody["boilerEfficiency"] - (0.1 * (requestBody["bedAshUnburntCarbon"] - 9) * requestBody["coalAsh"] * 80.77 / requestBody["coalGCV"])) / 100.0) - requestBody["turbineHeatRate"] / (requestBody["boilerEfficiency"] / 100.0) 
	requestBody["thr_dev_due_to_dry_flue_gas_loss_corrected"] = requestBody["hr_dev_due_to_dry_flue_gas_loss"] - 0.11
	requestBody["thr_dev_due_to_wet_flue_gas_loss_corrected"] = requestBody["hr_dev_due_to_wet_flue_gas_loss"] + 0.6
	requestBody["avg_back_press"] = (requestBody["CondenserVacuum"] + 100) / 100.0
	requestBody["condenser_ct_range"] = requestBody["condenserCondensateOutletTemp"] - requestBody["condenserCondensateInletTemp"]
	requestBody["actual_vacuum_deviation_kpa"] = (iapws97._PSat_T(T=(requestBody["condenserCondensateInletTemp"]+requestBody["condenser_ct_range"]+requestBody["condenserTTD"] +273))) * 10.0 
	if requestBody["load"] < 270.0:
		requestBody["corr_fac_01"] = 100.0 / (100.0 - 78.86 * (requestBody["actual_vacuum_deviation_kpa"] - 0.1033))
	else:
		requestBody["corr_fac_01"] = 100.0 / (100.0 - 63.09 * (requestBody["actual_vacuum_deviation_kpa"] - 0.1033))
	requestBody["cw_hr_dev_01"] = requestBody["turbineHeatRate"] * (requestBody["corr_fac_01"] - 1)
	requestBody["predicted_vacuum_deviation_kpa"] = (iapws97._PSat_T(T=(33+requestBody["condenser_ct_range"]+requestBody["condenserTTD"] +273))) * 10.0 
	if requestBody["load"] < 270.0:
		requestBody["corr_fac_02"] = 100.0 / (100.0 - 78.86 * (requestBody["predicted_vacuum_deviation_kpa"] - 0.1033))
	else:
		requestBody["corr_fac_02"] = 100.0 / (100.0 - 63.09 * (requestBody["predicted_vacuum_deviation_kpa"] - 0.1033))
	requestBody["cw_hr_dev_02"] = requestBody["turbineHeatRate"] * (requestBody["corr_fac_02"] - 1)
	requestBody["thr_dev_due_to_cond_cw_inlet_temp"] = requestBody["cw_hr_dev_01"] - requestBody["cw_hr_dev_02"]
	requestBody["gross_heat_rate_accounted_loss"] = requestBody["thr_dev_due_to_load"] + requestBody["thr_dev_due_to_msp"] + requestBody["thr_dev_due_to_mst"] + requestBody["thr_dev_due_to_ipt_il_tmp"] + requestBody["thr_dev_due_to_cond_vac"] + requestBody["thr_dev_due_to_sh_spray"] + requestBody["thr_dev_due_to_rh_spray"] + requestBody["thr_dev_due_to_fw_temp"] + requestBody["thr_dev_due_to_make_up_flow"] + requestBody["thr_dev_due_to_hp_turbine_efficiency"] + requestBody["thr_dev_due_to_ip_turbine_efficiency"] + requestBody["thr_dev_due_to_cond_cw_inlet_temp"] + requestBody["thr_dev_due_to_UBC_fly_ash"] + requestBody["thr_dev_due_to_UBC_bed_ash"] + requestBody["thr_dev_due_to_dry_flue_gas_loss_corrected"] + requestBody["thr_dev_due_to_wet_flue_gas_loss_corrected"]
	requestBody["gross_heat_rate_unaccounted_loss"] = (requestBody["gross_heat_rate"] - requestBody["gross_heat_rate_accounted_loss"]) - 2151

	return requestBody

def get_relationship_between_input_output_jsw_specific(function_name, response_body):
	funcString = inspect.getsource(function_name)
	to_reverse_string = []
	for line in funcString.splitlines():
		# print (line)
		if (line) and (line.strip()
		) and ("def" not in line) and (line.strip()[0] != "#"):
			pLine = line.replace("result", "res")
			to_reverse_string.append(pLine.strip())
	# print (to_reverse_string)
	graph = {}
	reversed_function = to_reverse_string[::-1]
	for line in reversed_function:
		if "=" in line:
			lhs = line.split("=", 1)[0]
			rhs = line.split("=", 1)[1]
			# if "IAPWS97" in rhs:
			count = 0
			lhsWord = ""
			rhsWord = ""
			for letter in lhs:
				if letter == '"':
					count = count + 1
				if count % 2 == 0:
					dontAppend = 0
				else:
					lhsWord = lhsWord + letter
			for letter in rhs:
				if letter == '"':
					count = count + 1
				if count % 2 == 0:
					dontAppend = 0
				else:
					rhsWord = rhsWord + letter
			# print (rhsWord, lhsWord)
			depends = rhsWord.split('"')
			notDepends = lhsWord.split('"')
			depends = list(set([dep for dep in depends if dep]))
			notDepends = list(set([dep for dep in notDepends if dep]))
			# print (depends, notDepends)
			for nd in notDepends:
				if nd not in graph.keys():
					if depends:
						graph[nd] = depends
				else:
					for k,v in graph.items():
						for v2 in v:
							if nd == v2:
								# print(nd, v2, depends)
								graph[k] = graph[k] + depends
								graph[k] = list(set(graph[k]))
	# print (graph)
	requiredGraph = {}
	for k,v in graph.items():
		for v2 in v:
			if v2 not in requiredGraph.keys():
				requiredGraph[v2] = ["gross_heat_rate"]
			# requiredGraph[v2].append(k)
	# print (json.dumps(requiredGraph, indent=4))
	if "relationship" in response_body:
		for k,v in requiredGraph.items():
			if k in response_body["relationship"].keys():
				print (k)
				response_body["relationship"][k] = response_body["relationship"][k] + v 
			else:
				response_body["relationship"][k] = v
	print (json.dumps(response_body, indent=4))
	return response_body

@app.route('/efficiency/jsw_specific_thr_dev', methods=['POST'])
def jsw_specific_thr_dev():
	print ("came to jsw specific thr dev api")
	request_body = request.json

	response_body = jsw_specific_thr_dev_calculations(request_body)

	response_body =  get_relationship_between_input_output(jsw_specific_thr_dev_calculations, response_body)
	
	response_body = get_relationship_between_input_output_jsw_specific(thr_pressureInMpa_calcs, response_body)

	return response_body



@app.route('/efficiency/turbineSide', methods=['POST'])
def turbineSide():
	request_body = json.loads(request.json)
	print (request_body, type(request_body))
	response_body = {}

	request_body["hph_5_extraction_press_h_side"] = request_body["hph_5_il_extraction_press"] - 1.6
	request_body["hph_5_extraction_temp_h_side"] = request_body["hph_5_il_extraction_temp"] - 1.3
	request_body["hph_4_extraction_press_h_side"] = request_body["hph_4_il_extraction_press"] - 0.88
	request_body["hph_4_extraction_temp_h_side"] = request_body["hph_4_il_extraction_temp"] - 1.1
	request_body["deaerator_steam_press_h_side"] = request_body["dea_extraction_press"] - 0.88
	request_body["deaerator_extraction_temp_h_side"] = request_body["dea_extraction_temp"] - 1.1
	request_body["deaerator_outlet_temp"] = request_body["hph_4_fw_il_temp"] - 1.9
	request_body["deaerator_shell_press"] = request_body["dea_extraction_press"]

	request_body["extraction_4_pres_turbine_end"] = ((IAPWS97(T=(request_body["lph_2_il_extraction_temp"] + 273),x=1).P) * 10.1972) - 1 
	request_body["extraction_4_temp_lph_end"] = request_body["lph_2_il_extraction_temp"] - 0.5
	request_body["extraction_4_pres_hph_end"] = ((IAPWS97(T=(request_body["extraction_4_temp_lph_end"] + 273),x=1).P) * 10.1972) - 1

	request_body["extraction_5_pres_turbine_end"] = ((IAPWS97(T=(request_body["lph_1_il_extraction_temp"] + 273),x=1).P) * 10.1972) - 1 
	request_body["extraction_5_temp_lph_end"] = request_body["lph_1_il_extraction_temp"] - 0.5
	request_body["extraction_5_pres_hph_end"] = ((IAPWS97(T=(request_body["extraction_5_temp_lph_end"] + 273),x=1).P) * 10.1972) - 1

	request_body["condenser_back_pressure"] =  ((IAPWS97(T=(request_body["turbine_exhaust_steam_temp"] + 273),x=1).P) * 10.1972) #not applied -1 coz this is in ata

	request_body["cep_discharge_temp"] = request_body["lph_1_il_fw_temp"]


	request_body["main_steam_enthalpy"] = IAPWS97(T=(request_body["main_steam_temp"] + 273), P=(((request_body["main_steam_press"] + 1) / 10.1972))).h
	request_body["hph_5_fw_ol_enthalpy"] = IAPWS97(T=(request_body["hph_5_fw_ol_temp"] + 273), P=(((request_body["eco_fw_il_press"] + 1) / 10.1972))).h
	request_body["hph_5_fw_il_enthalpy"] = IAPWS97(T=(request_body["hph_4_fw_ol_temp"] + 273), P=(((request_body["eco_fw_il_press"] + 1) / 10.1972))).h
	request_body["hph_5_fw_drain_enthalpy"] = IAPWS97(T=(request_body["hph_5_drip_ol_temp"] + 273), P=(((request_body["hph_5_extraction_press_h_side"] + 1) / 10.1972))).h
	request_body["hph_4_fw_il_enthalpy"] = IAPWS97(T=(request_body["hph_4_fw_il_temp"] + 273), P=(((request_body["bfp_discharge_press"] + 1) / 10.1972))).h
	request_body["hph_4_fw_drain_enthalpy"] = IAPWS97(T=(request_body["hph_4_drip_ol_temp"] + 273), P=(((request_body["hph_4_extraction_press_h_side"] + 1) / 10.1972))).h
	request_body["deaerator_condensate_il_enthalpy"] = IAPWS97(T=(request_body["dea_condensate_il_temp"] + 273), P=(((request_body["dea_condensate_il_press"] + 1) / 10.1972))).h

	request_body["deaerator_condensate_ol_enthalpy"] = IAPWS97(T=(request_body["deaerator_outlet_temp"] + 273), x=0).h
	request_body["make_up_water_enthalpy"] = IAPWS97(T=(request_body["dea_makeup_water_temp"] + 273), x=0).h

	request_body["extraction_1_hph_5_steam_enthalpy"] = IAPWS97(T=(request_body["hph_5_extraction_temp_h_side"] + 273), P=(((request_body["hph_5_extraction_press_h_side"] + 1) / 10.1972))).h
	request_body["extraction_2_hph_4_steam_enthalpy"] = IAPWS97(T=(request_body["hph_4_extraction_temp_h_side"] + 273), P=(((request_body["hph_4_extraction_press_h_side"] + 1) / 10.1972))).h
	request_body["extraction_3_deaerator_steam_enthalpy"] = IAPWS97(T=(request_body["deaerator_extraction_temp_h_side"] + 273), P=(((request_body["deaerator_steam_press_h_side"] + 1) / 10.1972))).h
	request_body["process_steam_enthalpy"] = IAPWS97(T=(request_body["process_steam_temp"] + 273), P=(((request_body["process_steam_press"] + 1) / 10.1972))).h
	request_body["extraction_1_turbine_end_steam_enthalpy"] = IAPWS97(T=(request_body["hph_5_il_extraction_temp"] + 273), P=(((request_body["hph_5_il_extraction_press"] + 1) / 10.1972))).h
	request_body["extraction_2_turbine_end_steam_enthalpy"] = IAPWS97(T=(request_body["hph_4_il_extraction_temp"] + 273), P=(((request_body["hph_4_il_extraction_press"] + 1) / 10.1972))).h
	request_body["lph_1_condensate_il_enthalpy"] = IAPWS97(T=(request_body["lph_1_il_fw_temp"] + 273), P=(((request_body["dea_condensate_il_press"] + 1) / 10.1972))).h
	request_body["lph_1_drain_enthalpy"] = IAPWS97(T=(request_body["lph_1_drain_temp"] + 273), P=(((request_body["extraction_4_pres_turbine_end"] + 1) / 10.1972))).h
	request_body["lph_2_condensate_il_enthalpy"] = IAPWS97(T=(request_body["lph_1_ol_fw_temp"] + 273), P=(((request_body["dea_condensate_il_press"] + 1) / 10.1972))).h
	request_body["lph_2_drain_enthalpy"] = IAPWS97(T=(request_body["lph_2_drain_temp"] + 273), P=(((request_body["extraction_4_pres_turbine_end"] + 1) / 10.1972))).h



	request_body["ms_inlet_ext_1_stage_constant_entropy"] = IAPWS97(T=(request_body["main_steam_temp"] + 273), P=(((request_body["main_steam_press"] + 1) / 10.1972))).s
	request_body["ms_inlet_ext_1_stage_isentropic_temp"] = (IAPWS97(s=(request_body["ms_inlet_ext_1_stage_constant_entropy"]), P=(((request_body["hph_5_il_extraction_press"] + 1) / 10.1972))).T) - 273 #iawps returns kelvin, -273 for celsius conversion
	request_body["ms_inlet_ext_1_stage_isentropic_enthalpy"] = IAPWS97(T=(request_body["ms_inlet_ext_1_stage_isentropic_temp"] + 273), P=(((request_body["hph_5_il_extraction_press"] + 1) / 10.1972))).h
	request_body["ms_inlet_ext_1_stage_actual_heat_drop"] = request_body["main_steam_enthalpy"] - request_body["extraction_1_hph_5_steam_enthalpy"]
	request_body["ms_inlet_ext_1_stage_isentropic_heat_drop"] = request_body["main_steam_enthalpy"] - request_body["ms_inlet_ext_1_stage_isentropic_enthalpy"]
	request_body["ms_inlet_ext_1_stage_isentropic_efficiency"] = request_body["ms_inlet_ext_1_stage_actual_heat_drop"] * 100 / request_body["ms_inlet_ext_1_stage_isentropic_heat_drop"]


	request_body["ext_1_ext_2_stage_constant_entropy"] = IAPWS97(T=(request_body["hph_5_il_extraction_temp"] + 273), P=(((request_body["hph_5_extraction_press_h_side"] + 1) / 10.1972))).s
	request_body["ext_1_ext_2_stage_isentropic_temp"] = (IAPWS97(s=(request_body["ext_1_ext_2_stage_constant_entropy"]), P=(((request_body["hph_4_il_extraction_press"] + 1) / 10.1972))).T) - 273 #iawps returns kelvin, -273 for celsius conversion
	request_body["ext_1_ext_2_stage_isentropic_enthalpy"] = IAPWS97(T=(request_body["ext_1_ext_2_stage_isentropic_temp"] + 273), P=(((request_body["hph_4_il_extraction_press"] + 1) / 10.1972))).h
	request_body["ext_1_ext_2_stage_actual_heat_drop"] = request_body["extraction_1_hph_5_steam_enthalpy"] - request_body["extraction_2_hph_4_steam_enthalpy"]
	request_body["ext_1_ext_2_stage_isentropic_heat_drop"] = request_body["extraction_1_hph_5_steam_enthalpy"] - request_body["ext_1_ext_2_stage_isentropic_enthalpy"]
	request_body["ext_1_ext_2_stage_isentropic_efficiency"] = request_body["ext_1_ext_2_stage_actual_heat_drop"] * 100 / request_body["ext_1_ext_2_stage_isentropic_heat_drop"]


	request_body["ext_2_ext_3_stage_constant_entropy"] = IAPWS97(T=(request_body["hph_4_il_extraction_temp"] + 273), P=(((request_body["hph_4_il_extraction_press"] + 1) / 10.1972))).s
	request_body["ext_2_ext_3_stage_isentropic_temp"] = (IAPWS97(s=(request_body["ext_2_ext_3_stage_constant_entropy"]), P=(((request_body["dea_extraction_press"] + 1) / 10.1972))).T) - 273 #iawps returns kelvin, -273 for celsius conversion
	request_body["ext_2_ext_3_stage_isentropic_enthalpy"] = IAPWS97(s=(request_body["ext_2_ext_3_stage_constant_entropy"]), P=(((request_body["dea_extraction_press"] + 1) / 10.1972))).h
	request_body["ext_2_ext_3_stage_actual_heat_drop"] = request_body["extraction_2_hph_4_steam_enthalpy"] - request_body["extraction_3_deaerator_steam_enthalpy"]
	request_body["ext_2_ext_3_stage_isentropic_heat_drop"] = request_body["extraction_2_hph_4_steam_enthalpy"] - request_body["ext_2_ext_3_stage_isentropic_enthalpy"]
	request_body["ext_2_ext_3_stage_isentropic_efficiency"] = request_body["ext_2_ext_3_stage_actual_heat_drop"] * 100 / request_body["ext_2_ext_3_stage_isentropic_heat_drop"]
	request_body["extraction_3_enthalpy"] = IAPWS97(x=(request_body["ext_3_dryness_fraction"]), P=(((request_body["extraction_4_pres_turbine_end"] + 1) / 10.1972))).h


	request_body["ext_3_ext_4_stage_constant_entropy"] = IAPWS97(T=(request_body["dea_extraction_temp"] + 273), P=(((request_body["dea_extraction_press"] + 1) / 10.1972))).s
	request_body["ext_3_ext_4_stage_isentropic_temp"] = (IAPWS97(s=(request_body["ext_3_ext_4_stage_constant_entropy"]), P=(((request_body["extraction_4_pres_turbine_end"] + 1) / 10.1972))).T) - 273 #iawps returns kelvin, -273 for celsius conversion
	request_body["ext_3_ext_4_stage_isentropic_enthalpy"] = IAPWS97(s=(request_body["ext_3_ext_4_stage_constant_entropy"]), P=(((request_body["extraction_4_pres_turbine_end"] + 1) / 10.1972))).h
	request_body["ext_3_ext_4_stage_actual_heat_drop"] = request_body["extraction_3_deaerator_steam_enthalpy"] - request_body["extraction_3_enthalpy"]
	request_body["ext_3_ext_4_stage_isentropic_heat_drop"] = request_body["extraction_3_deaerator_steam_enthalpy"] - request_body["ext_3_ext_4_stage_isentropic_enthalpy"]
	request_body["ext_3_ext_4_stage_isentropic_efficiency"] = request_body["ext_3_ext_4_stage_actual_heat_drop"] * 100 / request_body["ext_3_ext_4_stage_isentropic_heat_drop"]
	request_body["extraction_4_enthalpy"] = IAPWS97(x=(request_body["ext_4_dryness_fraction"]), P=(((request_body["extraction_5_pres_turbine_end"] + 1) / 10.1972))).h


	request_body["ext_4_ext_5_stage_constant_entropy"] = IAPWS97(h=(request_body["extraction_3_enthalpy"]), P=(((request_body["extraction_4_pres_turbine_end"] + 1) / 10.1972))).s
	request_body["ext_4_ext_5_stage_isentropic_temp"] = (IAPWS97(s=(request_body["ext_4_ext_5_stage_constant_entropy"]), P=(((request_body["extraction_5_pres_turbine_end"] + 1) / 10.1972))).T) - 273 #iawps returns kelvin, -273 for celsius conversion
	request_body["ext_4_ext_5_stage_isentropic_enthalpy"] = IAPWS97(s=(request_body["ext_4_ext_5_stage_constant_entropy"]), P=(((request_body["extraction_5_pres_turbine_end"] + 1) / 10.1972))).h
	request_body["ext_4_ext_5_stage_actual_heat_drop"] = request_body["extraction_3_enthalpy"] - request_body["extraction_4_enthalpy"]
	request_body["ext_4_ext_5_stage_isentropic_heat_drop"] = request_body["extraction_3_enthalpy"] - request_body["ext_4_ext_5_stage_isentropic_enthalpy"]
	request_body["ext_4_ext_5_stage_isentropic_efficiency"] = request_body["ext_4_ext_5_stage_actual_heat_drop"] * 100 / request_body["ext_4_ext_5_stage_isentropic_heat_drop"]
	request_body["extraction_5_enthalpy"] = IAPWS97(x=(request_body["ext_5_dryness_fraction"]), P=(((request_body["condenser_back_pressure"]) / 10.1972))).h


	request_body["ext_5_lph_exhaust_stage_constant_entropy"] = IAPWS97(h=(request_body["extraction_4_enthalpy"]), P=(((request_body["extraction_5_pres_turbine_end"] + 1) / 10.1972))).s
	request_body["ext_5_lph_exhaust_stage_isentropic_temp"] = (IAPWS97(s=(request_body["ext_5_lph_exhaust_stage_constant_entropy"]), P=(((request_body["condenser_back_pressure"]) / 10.1972))).T) - 273 #iawps returns kelvin, -273 for celsius conversion
	request_body["ext_5_lph_exhaust_stage_isentropic_enthalpy"] = IAPWS97(s=(request_body["ext_5_lph_exhaust_stage_constant_entropy"]), P=(((request_body["condenser_back_pressure"]) / 10.1972))).h
	request_body["ext_5_lph_exhaust_stage_actual_heat_drop"] = request_body["extraction_4_enthalpy"] - request_body["extraction_5_enthalpy"]
	request_body["ext_5_lph_exhaust_stage_isentropic_heat_drop"] = request_body["extraction_4_enthalpy"] - request_body["ext_5_lph_exhaust_stage_isentropic_enthalpy"]
	request_body["ext_5_lph_exhaust_stage_isentropic_efficiency"] = request_body["ext_5_lph_exhaust_stage_actual_heat_drop"] * 100 / request_body["ext_5_lph_exhaust_stage_isentropic_heat_drop"]


	request_body["combined_heat_drop"] = request_body["ms_inlet_ext_1_stage_actual_heat_drop"] + request_body["ext_1_ext_2_stage_actual_heat_drop"] + request_body["ext_2_ext_3_stage_actual_heat_drop"] + request_body["ext_3_ext_4_stage_actual_heat_drop"] + request_body["ext_4_ext_5_stage_actual_heat_drop"] + request_body["ext_5_lph_exhaust_stage_actual_heat_drop"] 

	request_body["combined_isentropic_heat_drop"] = request_body["ms_inlet_ext_1_stage_isentropic_heat_drop"] + request_body["ext_1_ext_2_stage_isentropic_heat_drop"] + request_body["ext_2_ext_3_stage_isentropic_heat_drop"] + request_body["ext_3_ext_4_stage_isentropic_heat_drop"] + request_body["ext_4_ext_5_stage_isentropic_heat_drop"] + request_body["ext_5_lph_exhaust_stage_isentropic_heat_drop"] 

	request_body["combined_isentropic_efficiency"] = request_body["combined_heat_drop"] * 100 / request_body["combined_isentropic_heat_drop"]



	return json.dumps(request_body)


def get_thr_dev_tags(unitId, system_name):
	thr_dev_tags = []
	descriptiondict={}
	endTime = int((time.time()*1000) + (5.5*60*60*1000))
	fifteen_days_ms = 15 * 24 * 60 * 60 * 1000
	startTime = endTime - fifteen_days_ms
	
	print (unitId, system_name)
	metric_name = unitId+"_"+str(system_name)+"_asset_manager"
	query = {"metrics":[{"tags":{},"name":metric_name,"group_by":[{"name":"tag","tags":["relatedTo","parameter","calculationType","dataTagId","measureUnit"]}],"limit":"1","aggregators":[{"name":"avg","sampling":{"value":"1","unit":"years"}}]}],"plugins":[],"cache_time":0,"start_absolute": startTime, "end_absolute":endTime}

	res = requests.post(config['api']['query'],json=query).json()
	# print (json.dumps(res, indent=4), "res")

	for result in res["queries"][0]["results"]:
		# print (json.dumps(result, indent=4))
		if result["group_by"][0]["group"]["calculationType"] == "desDev":
			thr_dev_tags.append(result["group_by"][0]["group"]["dataTagId"])
			descriptiondict[result["group_by"][0]["group"]["dataTagId"]]=result["group_by"][0]["group"]["parameter"]
			
			
	thr_dev_tags = [tags for tags in thr_dev_tags if " " not in tags]

	return thr_dev_tags,descriptiondict


BOILER_SYSTEM_NAMES = ["boiler", "afbc", "pcfb", "cfbc"]
TURBINE_SYSTEM_NAMES = ["turbine"]



@app.route('/efficiency/waterfall', methods=['POST'])
def waterfall():
	print ("came to waterfall api")
	requestBody = request.json
	print (requestBody)
	unitId = requestBody["unitid"]
	requested_system = requestBody["systemName"]
	before_start_time = requestBody["before_start_time"]
	before_end_time = requestBody["before_end_time"]
	after_start_time = requestBody["after_start_time"]
	after_end_time = requestBody["after_end_time"]

	mapping_config = fetch_efficiency_mapping(unitId)
	# print (json.dumps(mapping_config, indent=4))
	if mapping_config:
		for conf in mapping_config:
			for k,v in conf["output"].items():
				# print (k)
				if "turbine" in k.lower() or "boiler" in k.lower() or "plant" in k.lower():
					for single_system_conf in conf["output"][k]:
							# print (single_system_conf)
							# print (single_system_conf["systemName"])
							# print (requested_system)
							# print (single_system_conf["systemName"] == requested_system)
						# try:
							if (isinstance(single_system_conf, dict)) and (single_system_conf["systemName"] == requested_system):
								for name in BOILER_SYSTEM_NAMES:
									if name in requested_system.lower():
										required_tags = list(single_system_conf["outputs"].values())
										print (required_tags)

										df_before = get_data_epoch(required_tags, before_start_time, before_end_time)
										
										# print("\n" + "-"*20 + " DF Before (get_data_epoch) " + "-"*20 + "\n")
										# print(df_before)
										
										df_after = get_data_epoch(required_tags, after_start_time, after_end_time)

										# print("\n" + "-"*20 + " DF After (get_data_epoch)" + "-"*20 + "\n")
										# print(df_after)

										# if (len(df_after.columns) != len(df_before.columns)):
										#     return json.dumps(["data issues"]), 500
										# else:
										df_result = pd.DataFrame()
										# df_before = pd.DataFrame(df_before.mean()).T
										# df_after = pd.DataFrame(df_after.mean()).T

										df_before = df_before.replace(0, np.nan).mean().to_frame().T
										df_after  = df_after.replace(0, np.nan).mean().to_frame().T
										
										# print("\n" + "-"*20 + " DF Before Mean " + "-"*20 + "\n")
										# print(df_before)

										# print("\n" + "-"*20 + " DF After Mean" + "-"*20 + "\n")
										# print(df_after)
										# df_result.columns = df_before.columns

										for tag in required_tags:
											if "time" not in tag and "oiler" not in tag and "ffiency" not in tag and "otal" not in tag:
												# df_result[tag] = df_after[tag] - df_before[tag]
												for k,v in single_system_conf["outputs"].items():
													# print (tag, v)
													if tag == v:
														# print (tag, tag not in df_before.columns, tag not in df_after.columns)
														if (tag not in df_before.columns) and (tag in df_after.columns):
															df_result[k] = 0 - df_after[tag]
														elif (tag in df_before.columns) and (tag not in df_after.columns):
															df_result[k] = df_before[tag]
														elif (tag not in df_before.columns) and (tag not in df_after.columns):
															df_result[k] = 0.0
														else:
															df_result[k] = df_before[tag] - df_after[tag]

										print ("\n\n")

										# print("-"*20 + " DF Final Result" + "-"*20 + "\n")
										# print(df_result)    

										final_result_in_dict = df_result.to_dict(orient="records")[0]
										
										totalizer = 0.0
										for k,v in final_result_in_dict.items():
											totalizer = totalizer + v

										for tag in required_tags:
											if "oiler" in tag and "fficiency" in tag:
												final_result_in_dict["before_boiler_efficiency"] = df_before[tag].values[0]
												final_result_in_dict["after_boiler_efficiency"] = df_after[tag].values[0]

										
										print(final_result_in_dict)
										return json.dumps([final_result_in_dict]), 201
								
								for name in TURBINE_SYSTEM_NAMES:
									if name in requested_system.lower():
										print("turbine system detected")
										print("This thr waterfall api call does nothign other than provide before and after values. no insights")
										required_tags = list([single_system_conf["outputs"]["turbineHeatRate"]])

										#modifications made to include thr dev tags of each indivudal contribution  in waterfall 
										thr_des_dev_tags,thr_description = get_thr_dev_tags(unitId, single_system_conf["systemName"])
										required_tags = required_tags + thr_des_dev_tags

										# print(required_tags)
										
										df_before = get_data_epoch(required_tags, before_start_time, before_end_time)
										df_after = get_data_epoch(required_tags, after_start_time, after_end_time)

										# print (df_after)
										# print (df_before)
										# print (df_after.columns)
										# print (df_before.columns)
										# print (set(df_after.columns).intersection(df_before.columns))

										if (len(df_after.columns) != len(df_before.columns)):
											return json.dumps(["data issues"]), 500
										
										else:

											df_result = pd.DataFrame()
											
											# df_before = pd.DataFrame(df_before.mean()).T
											# df_after = pd.DataFrame(df_after.mean()).T
											df_before = pd.DataFrame(df_before.replace(0, np.nan).mean()).T
											df_after  = pd.DataFrame(df_after.replace(0, np.nan).mean()).T

											

											for tag in required_tags:
												if "time" not in tag and "otal" not in tag and "Turbine_HeatRate" not in tag:
													try:
														# df_result[tag] = df_after[tag] - df_before[tag]
														if not df_before.empty and not df_after.empty:
															df_result[tag] = df_after[tag] - df_before[tag]
														else:
															df_result[tag] = 0.0
													except:
														df_result[tag] = 0.0
												# for k,v in [single_system_conf["outputs"]["turbineHeatRate"]]:
												#     print (tag, v)
												#     if tag == v:
												#         df_result[tag] = df_after[tag] - df_before[tag]

											print ("\n\n")
											# print (df_result)

											if df_result.empty:
												df_result = pd.DataFrame([[0.0] * len(df_result.columns)], columns=df_result.columns)

											# print("-"*20 + " DF Final Result" + "-"*20 + "\n")
											# print(df_result)
											# print (required_tags[0])
											# print (df_after)
											# print (df_before)
											final_result_in_dict = df_result.to_dict(orient="records")[0]
											final_result_in_dict["before_turbine_heat_rate"] = df_before[required_tags[0]].values[0]
											final_result_in_dict["after_turbine_heat_rate"] = df_after[required_tags[0]].values[0]
											actual_diff = final_result_in_dict["after_turbine_heat_rate"] - final_result_in_dict["before_turbine_heat_rate"]

											#below code snipper is to handle Nan values in end result reponse result. 
											for k,v in final_result_in_dict.items():
												if v != v:
													final_result_in_dict[k] = 0.0

											# print (json.dumps(final_result_in_dict, indent=4))
											final_result_in_dict=replace_with_description(final_result_in_dict,thr_description)
											final_result_in_dict = add_hr_reconciliation(final_result_in_dict)

											result_exclude_params = {}
											if "exclude_params" in single_system_conf:
												for k,v in final_result_in_dict.items():
													for k2,v2 in single_system_conf["thr_outputs"].items():
														if v2 == k[:-8]:
															# print (single_system_conf["thr_dev_params"][k2])
															try:
																if "Thr Dev Due To" in single_system_conf["thr_dev_params"][k2]:
																	result_exclude_params[single_system_conf["thr_dev_params"][k2][15:]] = v
															except Exception as e:
																print (e)
																pass

												result_exclude_params["before_turbine_heat_rate"] = final_result_in_dict["before_turbine_heat_rate"]
												result_exclude_params["after_turbine_heat_rate"] = final_result_in_dict["after_turbine_heat_rate"]

												final_result_in_dict = result_exclude_params
												final_result_in_dict=replace_with_description(final_result_in_dict,thr_description)
												final_result_in_dict = add_hr_reconciliation(final_result_in_dict)




											return json.dumps([final_result_in_dict]), 201






						# except Exception as e:
						#     print (e)
						#     pass


								# print (final_result_in_dict["previous_blr_eff"] - final_result_in_dict["following_blr_eff"] - totalizer)
								


	else:
		print ("Issues with mapping file")
		return json.dumps(["Issues with mapping file"]), 500





	return "", 500

# Function for fuelTco
@app.route('/efficiency/tcopredictor', methods=['POST'])
def evaluateTCO():
	
	req = request.json
	effURL = "http://0.0.0.0:5068/efficiency/"
	#effURL = config["api"]["meta"].strip(':3000/exactapi') + ':5068/efficiency/'
	inputs = {"fuelName" : "Fuel Name", "fuelMix" : "Fuel Mix", "fuelProps":"Fuel Props", "addToCompare" : "Add to Compare", "properties" : []}
	inputs1 = {"genInputs" : [], "proximate" : [], "ultimate" : [], "fuelGen" : []}
	inputs1["genInputs"] = [
		  {	
			"field" : "Boiler Load",
			"name" : "boilerSteamFlow",
			"measureUnit" : "TPH",
			"value" : 69.26,
			"range" : [0,200],
			"display" : True
		  },
		  {	
			"field" : "Flue Gas Outlet O2 Percentage",
			"name" : "aphFlueGasOutletO2",
			"measureUnit" : "%",
			"value" : 5.458,
			"range" : [0,100],
			"display" : True
		  },
		  {	
			"field" : "APH Exit Flue Gas Temperature",
			"name" : "aphFlueGasOutletTemp",
			"measureUnit" : "Deg C",
			"value" : 147.548,
			"range" : [0,200],
			"display" : True
		  },
		  {	
			"field" : "Ambient Air Temperature",
			"name" : "ambientAirTemp",
			"measureUnit" : "Deg C",
			"value" : 28.52,
			"range" : [0,300],
			"display" : True
		  },
		  {
			"field" : "Main Steam Temperature",
			"name" : "msTemp",
			"measureUnit" : "Deg C",
			"value" : 481.41,
			"range" : [0, 700],
			"display" : True
		  },
		  {	
			"field" : "Main Steam Pressure",
			"name" : "msPres",
			"measureUnit" : "mpa",
			"value" : 104.1,
			"range" : [0, 300],
			"display" : True
		  },
		  {	
			"field" : "Feedwater Temperature",
			"name" : "fwTemp",
			"measureUnit" : "Deg C",
			"value" : 159.9,
			"range" : [0, 300],
			"display" : True
		  },
		  {	
			"field" : "Air Humidity Factor",
			"name" : "airHumidityFactor",
			"measureUnit" : "-",
			"value" : 0.016,
			"range" : [0,100],
			"display" : False
		  },
		  {	
			"field" : "Loss Unaccounted",
			"name" : "LossUnaccounted",
			"measureUnit" : "%",
			"value" : 0.5,
			"range" : [0,20],
			"display" : False
		  },
		  {	
			"field" : "Loss Due To Radiation",
			"name" : "LossDueToRadiation",
			"measureUnit" : "%",
			"value" : 0.5,
			"range" : [0,20],
			"display" : False
		  },
		  {	
			"field" : "Other Plant Specific Losses",
			"name" : "Other_Losses_Plant_Specific_prc",
			"measureUnit" : "%",
			"value" : 0,
			"range" : [0,20],
			"display" : False
		  }
		]
	inputs1["proximate"] = [	
		  {	
			"field" : "Fixed Carbon",
			"name" : "coalFC",
			"measureUnit" : "%",
			"value" : 0,
			"range" : [0, 100]
		  },
		  {
			"field" : "Volatile Matter",
			"name" : "coalVM",
			"measureUnit" : "%",
			"value" : 0,
			"range" : [0, 100]
		  },
		  {	
			"field" : "Ash",
			"name" : "coalAsh",
			"measureUnit" : "%",
			"value" : 0,
			"range" : [0, 100]
		  },
		  {	
			"field" : "Total Moisture",
			"name" : "coalMoist",
			"measureUnit" : "%",
			"value" : 0,
			"range" : [0, 100]
		  },
		  {	
			"field" : "Calorific Value (GCV)",
			"name" : "coalGCV",
			"measureUnit" : "KCal/Kg",
			"value" : 0,
			"range" : [0, 10000]
		  }
		  
		]
	inputs1["ultimate"] = [	
		  {	
			"field" : "Carbon",
			"name" : "carbon",
			"measureUnit" : "%",
			"value" : 39.1,
			"range" : [0, 100]
		  },
		  {
			"field" : "Hydrogen",
			"name" : "hydrogen",
			"measureUnit" : "%",
			"value" : 3.14,
			"range" : [0, 100]
		  },
		  {	
			"field" : "Nitrogen",
			"name" : "nitrogen",
			"measureUnit" : "%",
			"value" : 0.72,
			"range" : [0, 100]
		  },
		  {	
			"field" : "Sulphur",
			"name" : "coalSulphur",
			"measureUnit" : "%",
			"value" : 0.8,
			"range" : [0, 100]
		  },
		  {	
			"field" : "Oxygen",
			"name" : "oxygen",
			"measureUnit" : "%",
			"value" : 11.29,
			"range" : [0, 100]
		  },
		  {	
			"field" : "Ash",
			"name" : "coalAsh",
			"measureUnit" : "%",
			"value" : 21.65,
			"range" : [0, 100]
		  },
		  {	
			"field" : "Total Moisture",
			"name" : "coalMoist",
			"measureUnit" : "%",
			"value" : 23.3,
			"range" : [0, 100]
		  },
		  {	
			"field" : "Calorific Value (GCV)",
			"name" : "coalGCV",
			"measureUnit" : "KCal/Kg",
			"value" : 3814.0,
			"range" : [0, 10000]
		  }
		  
		]
	inputs1["fuelGen"] = [
		{	
			"field" : "Landing Cost of Fuel",
			"name" : "landingCost",
			"measureUnit" : "Rs/Ton",
			"value" : 7000,
			"range" : [0, 20000]
		},
		{	
			"field" : "Fly Ash Carbon",
			"name" : "flyAshUnburntCarbon",
			"measureUnit" : "%",
			"value" : 10.84,
			"range" : [0,100]
			
		},
		{	
			"field" : "Bed Ash Carbon",
			"name" : "bedAshUnburntCarbon",
			"measureUnit" : "%",
			"value" : 4.0,
			"range" : [0,100]
		}
	]
	if req["requestType"] == "inputs":
		for item in inputs1["genInputs"]:
			item["type"] = "genInputs"
			inputs["properties"].append(item)
		for item in inputs1["proximate"]:
			item["type"] = "proximate"
			inputs["properties"].append(item)
		for item in inputs1["ultimate"]:
			item["type"] = "ultimate"
			inputs["properties"].append(item)
		for item in inputs1["fuelGen"]:
			item["type"] = "fuelGen"
			inputs["properties"].append(item)
		
		return inputs
	
	elif req["requestType"] == "proxToUltConv":
		# print "***Request to Prox To Ult conversion***"
		reqObj = {"type" : "type1"}
		resObj = {"fuelName" : req["fuelName"], "fuelIndex" : req["fuelIndex"], "properties" : []}
		
		for item in req["properties"]:
			reqObj[item["name"]] = item["value"]
		
		# print "** sending prox to ult request"
		# print "** Url: ", effURL + "proximatetoultimate"
		# print '["coalFC", "coalVM", "coalAsh", "coalMoist"]'
		# print "reqObj: ", json.dumps(reqObj, indent=4)
		
		fuelUltimateData = proximatetoultimate_index[str(reqObj["type"])](reqObj)
		'''
		# This is a request based route. It is failing. So, shifted to non-request based route. 
		fuelUltimateData = requests.post(effURL+"proximatetoultimate",json=reqObj)
		print "** Status code: ", fuelUltimateData.status_code
		if fuelUltimateData.status_code == 200:
			fuelUltimateData = fuelUltimateData.json()
			for item in inputs1["ultimate"]:
				k = {}
				if item["name"] in fuelUltimateData:
					k["name"] = item["name"]
					k["value"] = round(fuelUltimateData[item["name"]], 3)
					k["type"] = "ultimate"
				else:
					k["name"] = item["name"]
					k["value"] = reqObj[item["name"]]
					k["type"] = "ultimate"
					
				resObj["properties"].append(k)
		else:
			print "Fuel Ultimate Data::"
			print fuelUltimateData
		'''
		for item in inputs1["ultimate"]:
			k = {}
			if item["name"] in fuelUltimateData:
				k["name"] = item["name"]
				k["value"] = round(fuelUltimateData[item["name"]], 3)
				k["type"] = "ultimate"
			else:
				k["name"] = item["name"]
				k["value"] = reqObj[item["name"]]
				k["type"] = "ultimate"
				
			resObj["properties"].append(k)
		
		# print "*" * 10
		# print "Placeholder" 
		# print "*" * 10
		proxToUltData = 1
		return {"helpText" : "Returning ultimate values", "data" : resObj}
		
	elif req["requestType"] == "blendCalculation":
		blendResult = {}
		for item in req["fuelInputs"]:
			if item["valueType"] == "percentage":
				for key,val in item["properties"].items():
					# print "#" * 20
					# print val, item["value"]
					# print "#" * 20
					val = float(val) * float(item["value"]) * 0.01 
					blendResult[key] = round((blendResult[key] + val), 3) if blendResult.get(key) else round(val, 3)      
					
		return {"helpText" : "Fuel Ultimate Conversion Successful!", "data" : blendResult}
		
	elif req["requestType"] == "fuelTco":
		# print "Here in Fuel TCO"
		response = []
		result = []
		fuelRanking = []
		finalResponse = []
		# Dummy code Start Here
		dummyResponse = []
		count = 1
		for item in req["fuelInputs"]:
			dummy = {"results" : []}
			dummy["fuelName"] = item["fuelName"]
			dummy["results"].append({"field": "Boiler Efficiency", "measureUnit": "%", "name": "boilerEfficiency", "type": "fuelTco", "value": 80.19})
			dummy["results"].append({"field": "Total Fuel Flow", "measureUnit": "TPH", "name": "coalFlow", "type": "fuelTco", "value": 6.98})
			dummy["results"].append({"field": "Average Cost of Fuel", "measureUnit": "Rs/Hr", "name": "costOfFuel", "type": "fuelTco", "value": 10816.95})
			dummy["results"].append({"field": "Average Cost Per Unit Steam", "measureUnit": "Rs/Ton", "name": "costPerUnitSteam", "type": "fuelTco", "value": 190.26})
			dummy["results"].append({"field": "Fuel Ranking", "measureUnit" : " ", "name" : "rank", "type" : "fuelTco", "value" : count})
			dummyResponse.append(dummy)
			count += 1
		# Dummy code End Here
		for item in req["fuelInputs"]:
			resp = {"results" : []}
			effObj = {"type": "type9"}
			for genProp in req["generalInputs"]:
				effObj[genProp["name"]] = genProp["value"]
			for fuelProp in item["properties"]:
				effObj[fuelProp["name"]] = fuelProp["value"]
			  
			result.append(effObj) # Dummy one not required
			# calculate boiler efficiency here
			try:
				for k,v in effObj.items():
					try:
						effObj[k] = float(v)
					except:
						pass
					   
				# This is a request based route. It is failing. So, shifted to non-request based route.
				#effOutput = requests.post(effURL+"boiler",json=effObj)
				#effOutput = effOutput.json()
				
				effOutput = boilerEfficiency_index[str(effObj["type"])](effObj)
				effObj["boilerEfficiency"] = effOutput["boilerEfficiency"] * 0.01
				# print "@@" * 20
				#print json.dumps(effOutput, indent=4)
				# print "Boiler Efficiecy: ", effObj["boilerEfficiency"]
				for k,v in effObj.items():
					try:
						effObj[k] = float(v)
					except:
						pass
				#effObj["landingCost"] = float(effObj["landingCost"])
				#print "Eff Obj: "
				#print json.dumps(effObj, indent=4)
				# print "*&", "Got here"
				
				#fuelTcoOutput = requests.post(effURL+"coalCal",json=effObj)
				#print fuelTcoOutput.status_code
				#fuelTcoOutput = fuelTcoOutput.json()
				fuelTcoOutput = coalFlowCalculationNoRequest(effObj)
				# print "@@" * 20
				#float("-")
				resp["fuelName"] = item["fuelName"]
				resp["results"].append({"field": "Boiler Efficiency", "measureUnit": "%", "name": "boilerEfficiency", "type": "fuelTco", "value": round(effObj["boilerEfficiency"] * 100, 3)})
				resp["results"].append({"field": "Total Fuel Flow", "measureUnit": "TPH", "name": "coalFlow", "type": "fuelTco", "value": round(fuelTcoOutput["coalFlow"], 3)})
				resp["results"].append({"field": "Average Cost of Fuel", "measureUnit": "Rs/Hr", "name": "costOfFuel", "type": "fuelTco", "value": round(fuelTcoOutput["costOfFuel"], 3)})
				resp["results"].append({"field": "Average Cost Per Unit Steam", "measureUnit": "Rs/Ton", "name": "costPerUnitSteam", "type": "fuelTco", "value": round(fuelTcoOutput["costPerUnitSteam"], 3)})
				resp["results"].append({"field": "Fuel Ranking", "measureUnit" : "-", "name" : "rank", "type" : "fuelTco", "value" : "-"})
				response.append(resp)
				fuelRanking.append({"fuelName" : item["fuelName"], "val" : fuelTcoOutput["costPerUnitSteam"], "addToCompare" : item["addToCompare"] if (item["addToCompare"] != 0) else np.nan})
			except Exception as e:
				resp["fuelName"] = item["fuelName"]
				resp["results"].append({"field": "Boiler Efficiency", "measureUnit": "%", "name": "boilerEfficiency", "type": "fuelTco", "value": "-"})
				resp["results"].append({"field": "Total Fuel Flow", "measureUnit": "TPH", "name": "coalFlow", "type": "fuelTco", "value": "-"})
				resp["results"].append({"field": "Average Cost of Fuel", "measureUnit": "Rs/Hr", "name": "costOfFuel", "type": "fuelTco", "value": "-"})
				resp["results"].append({"field": "Average Cost Per Unit Steam", "measureUnit": "Rs/Ton", "name": "costPerUnitSteam", "type": "fuelTco", "value": "-"})
				resp["results"].append({"field": "Fuel Ranking", "measureUnit" : "-", "name" : "rank", "type" : "fuelTco", "value" : "-"})
				response.append(resp)
				fuelRanking.append({"fuelName" : item["fuelName"], "val" : float("-inf"), "addToCompare" : np.nan})
				#pass
		
		for z in fuelRanking:
			z["val"] = z["val"] * z["addToCompare"]
		fuelRanking = [z for z in fuelRanking if z["val"]==z["val"]]
		fuelRanking = sorted(fuelRanking, key=lambda d: d['val'], reverse=False)
	
		for fuel in fuelRanking:
			for match in response:
				if fuel["fuelName"] == match["fuelName"]:
					match["results"][-1]["value"] = fuelRanking.index(fuel) + 1
					finalResponse.append(match)
				
				
		# print "66" * 100
		# print fuelRanking
		# print json.dumps(response, indent=4)
		# print finalResponse
		# print "66" * 100
		#return {"helpText" : "Under Progress", "data" : response}
		return {"helpText" : " Under Progress", "data" : finalResponse}

@app.route('/efficiency/fuelratio', methods=['POST'])
def lastvalue():
	res = request.json
	# res = json.loads(res)
	print (res, type(res))
	unitId = res["unitId"]
	systemName =str( res["systemName"])
	url = config["api"]["meta"]+ '/units/'+unitId+'/forms?filter={"where":{"name":"'+systemName+'"}}'
	res = requests.get(url).json()
	tags = [tag["dataTagId"] for tag in res[0]["fields"] if ("coal flow" in tag["display"].lower() and "total" not in tag["display"].lower()) or ("gcv" in tag["display"].lower() and "average" not in tag["display"].lower()) or ("cost" in tag["display"].lower() and "average" not in tag["display"].lower())]
	print(tags)
	
	# n = max([int(tag["display"].lower().split("-")[-1][0]) for tag in res[0]["fields"] if "type-" in tag["display"].lower()])
	# n = max([int(tag["standardDescription"].lower().split()[-1][0]) for tag in res[0]["fields"] if "standardDescription" in tag])
	n = max([int(tag["standardDescription"].lower().split()[-1][0]) for tag in res[0]["fields"] if "standardDescription" in tag and tag["standardDescription"].lower().split()[-1][0].isdigit()])

	# values = {f"fuel {i}": {} for i in range(1, n + 1)} 
	cf = cst = gcv = 0 
	finalresult=[]
	for fuel_number in range(1, n+1):
		result={}
		# fuel_key = f"fuel {fuel_number}"
		for tag in res[0]["fields"] :
			# print(tag["dataTagId"])
			if f"FUEL_{fuel_number}" in tag["dataTagId"].upper() and "COAL_FLOW" in tag["dataTagId"].upper():
				print("tag in if ")
				# print(tag)
				result["name"]=tag["display"].split(" ")[0]+" Coal"
				try:
					result["Coal Flow"]= float(getLastValues([tag["dataTagId"]]).iloc[0,-1])
				except :
					result["Coal Flow"] =0
				cf += result["Coal Flow"]
			elif f"FUEL_{fuel_number}" in tag["dataTagId"].upper() and "COST" in tag["dataTagId"].upper():
				# result["name"]=tag["display"].split(" ")[0]+"coal"
				try:
					result["Coal Cost"]= float(getLastValues([tag["dataTagId"]]).iloc[0,-1])
				except:
					result["Coal Cost"] =0 
				cst+= result["Coal Cost"]
			elif f"FUEL_{fuel_number}" in tag["dataTagId"].upper() and "GCV" in tag["dataTagId"].upper():
				# result["name"]=tag["display"].split(" ")[0]+"coal"
				try:
					result["Coal Gcv"]= float(getLastValues([tag["dataTagId"]]).iloc[0,-1])
				except :
					result["Coal Gcv"] =0
				gcv+= result["Coal Gcv"]
		finalresult.append(result)

	finalresult = [{tag: round(value / cf * 100, 2) if "Coal Flow" in tag else value for tag, value in dicts.items()} for dicts in finalresult]

		
	# for fuel_number in range(1, n+1):
	#     fuel_key = f"fuel {fuel_number}"
	#     for tag in tags:
	#         if f"FUEL_{fuel_number}" in tag.upper() and "COAL_FLOW" in tag.upper():
				
	#             val = float(getLastValues([tag]).iloc[0,-1])
	#             print(val)
	#             values[fuel_key][f"Coal Flow"] = val 
	#             cf+= val 
	#         elif f"FUEL_{fuel_number}" in tag.upper() and "COST" in tag.upper():
	#             val = float(getLastValues([tag]).iloc[0,-1])
	#             values[fuel_key][f"Coal Cost"] = val
	#             cst+= val
	#         elif f"FUEL_{fuel_number}" in tag.upper() and "GCV" in tag.upper():
	#             val = float(getLastValues([tag]).iloc[0,-1])
	#             values[fuel_key][f"Coal Gcv"] = val
	#             gcv+= val
	# for fuel_key, fuel in values.items():
	#     coal_flow = fuel['Coal Flow']
	#     percentage = (coal_flow / cf) * 100
	#     fuel['Coal Flow'] = round(percentage, 2)
	# # for fuel_number in range(1, n+1):
	# #     fuel_key = f"fuel {fuel_number}"
	# #     values[fuel_key][f"coal Flow {fuel_number}"] = round((values[fuel_key][f"coal Flow {fuel_number}"]), 3)
	# #     values[fuel_key][f"Coal Cost {fuel_number}"] = round((values[fuel_key][f"Coal Cost {fuel_number}"]), 3)
	# #     values[fuel_key][f"Coal Gcv {fuel_number}"] = round((values[fuel_key][f"Coal Gcv {fuel_number}"]), 3)
	# result = [{"name": key, **value} for key, value in values.items()]
	result = json.dumps(finalresult)
	return result

@app.route('/efficiency/createfuel', methods=['POST'])
def addfuel():
	res = request.json
	# res = json.loads(res)
	print (res, type(res))

	unitId = res["unitId"]
	systemName = res["systemName"]
	fuelName = res["fuelName"]
	system = systemName[:-2]
	systemInstance = systemName[-1]

	url = config["api"]["meta"]+'/units/'+unitId+'/forms?filter={"where":{"system":"'+str(system)+'","systemInstance":'+str(systemInstance)+'}}'
	res = requests.get(url).json()
	prefix = getPrefix(unitId)
	# print(prefix)
	res[0]["typesOfFuel"]+= 1
	# print(res[0]["typesOfFuel"])
	prox_params = {'CoalFlow': {'dataTagId': '_COAL_FLOW',
		'display': ' Coal Flow (TPD)',
		"standardDescription": "Coal Flow",
		"createdBy":"user",
		'name': 'coal_flow',
		'range': [1, 100],
		'type': 'number',
		'units': '%'}, 'fc': {'dataTagId': '_FC',
		'display': ' Prox ARB FC',
		"standardDescription": "Fixed Carbon",
		"createdBy":"user",
		'name': 'fc',
		'range': [1, 100],
		'type': 'number',
		'units': '%'}, 'vm': {'dataTagId': '_VM',
		'display': ' Prox ARB VM',
		"standardDescription": "Volatile Matter",
		"createdBy":"user",
		'name': 'vm',
		'range': [1, 100],
		'type': 'number',
		'units': '%'}, 'TM': {'dataTagId': '_TM',
		'display': ' Prox ARB Total Moisture',
		"standardDescription": "Total Moisture",
		"createdBy":"user",
		'name': 'tot_moisture',
		'range': [1, 100],
		'type': 'number',
		'units': '%'}, 'SM': {'dataTagId': '_SM',
		'display': ' Prox ARB Surface Moisture',
		"standardDescription": "Surface Moisture",
		"createdBy":"user",
		'name': 'sur_moisture',
		'range': [1, 100],
		'type': 'number',
		'units': '%'}, 'IM': {'dataTagId': '_IM',
		'display': ' Prox ADB Inherent Moisture',
		"standardDescription": "Inherent Moisture",
		"createdBy":"user",
		'name': 'Inh_moisture',
		'range': [1, 100],
		'type': 'number',
		'units': '%'}, 'ash': {'dataTagId': '_ASH',
		"standardDescription": "Coal Ash",
		"createdBy":"user",
		'display': ' Prox ARB Ash',
		'name': 'ash',
		'range': [1, 100],
		'type': 'number',
		'units': '%'}, 'gcv': {'dataTagId': '_GCV',
		'display': ' Prox ARB GCV',
		"standardDescription": "Coal Gcv",
		"createdBy":"user",
		'name': 'gcv',
		'range': [2500, 5000],
		'type': 'number',
		'units': 'kCal'}, 'cost': {'dataTagId': '_COST',
		'display': ' Cost',
		"standardDescription": "Coal Cost",
		"createdBy":"user",
		'name': 'cost',
		'range': [1, 10000],
		'type': 'number',
		'units': 'Rs./Ton'}}
	if systemName == res[0]["system"]+" "+str(+res[0]["systemInstance"]):
		if res[0]["inputType"] == "proximate":
			for p in res[0]["coalParams"]["proximate"]:
				param = prox_params[p]
				param["dataTagId"] = prefix+systemName.replace(" ","_").upper()+"_FUEL_"+str(res[0]["typesOfFuel"])+param["dataTagId"]
				param["display"] = fuelName+param["display"]
				param["standardDescription"]= param["standardDescription"]+" "+str(res[0]["typesOfFuel"])
				res[0]["fields"].append(param)
	form = json.dumps(res[0])
	# print(form)
	sc = updateform(form)
	# sc=200
	if sc== 200:
		return {"success" : "Fuel has been added"}
	else:
		return {"failed" : "Fuel is not created"}

@app.route('/efficiency/fuelprediction', methods=['POST'])
def bestcombination():
	# start_time=time.time()
	res = request.json
	unitId = res["unitId"]
	systemName =str(res["systemName"])
	startTime = res["startTime"]
	endTime= res["endTime"]
	ConsiderationList = ["Coal Gcv", "Coal Flow", "Coal Cost","aux power"]
	displayList=["Date"]
	taglist={}
	columns_to_ffill=[]
	pattern_types = {
	"aux power": {"type": "aux power", "unit": "mW"},
	"boilerEfficiency": {"type": "boilerEfficiency", "unit": "%"},
	r'^Coal Flow \d+_percentage$': {"type": "fuelratios", "unit": "%"},
	r'^(?:.*direct|indirect)?costPerUnitSteam$': {"type": "costPerUnitSteam", "unit": "Rs/ton"},
	"CorrectedCostPerUnitSteam": {"type": "costPerUnitSteam", "unit": "Rs/ton"}}
	resultdict=[
		{
			"property": "color",
			"color": "green",
			"columns": ["correctedSteamCost"]
		},
		{
			"property": "scroll",
			"columns": displayList
		}
	]

	mapping_file_url = config["api"]["meta"]+'/units/'+unitId+'/boilerStressProfiles?filter={"where":{"type":"efficiencyMapping"}}'
	boilerres = requests.get(mapping_file_url)

	if boilerres.status_code == 200 and len(boilerres.json())!=0:
		mapping_file = boilerres.json()[0]
		mapping = mapping_file["output"]
		
		for boiler in mapping["boilerEfficiency"]:
			if boiler["systemName"] == systemName:
				# taglist.update(boiler["realtime"])
				taglist.update({"boilerSteamFlow":boiler["realtime"]["boilerSteamFlow"]})
				for key, value in boiler["coalCalOutputs"].items():
					taglist.update({key: [value]})
				if "boilerEfficiency" in boiler.get("outputs", {}):
					taglist.update({"boilerEfficiency": [boiler["outputs"]["boilerEfficiency"]]})
		if mapping.get("turbineHeatRate"):
			for turbine in mapping["turbineHeatRate"]:
				taglist.update({"TgInletflow":turbine["realtime"]["steamFlowMS"],"TgLoad":turbine["realtime"]["load"]})

					
	else:
		mapping = ""
	
	try:
		systemNum=systemName.split()[-1]
		FormMeta = config["api"]["meta"] + '/forms?filter={"where":{"unitsId":"'+ unitId +'","name":"Station ' +systemNum+ '"}}'
		FormMetares = requests.get(FormMeta)
		print(FormMeta)
		if FormMetares.status_code == 200 and len(FormMetares.json())!=0:
			FormMeta = FormMetares.json()[0]
			# taglist = {tag["standardDescription"]: [tag["dataTagId"]] for tag in FormMeta["fields"] if "standardDescription" in tag and tag.get("standardDescription") == "aux power"}
			for tag in FormMeta["fields"]:
				if "standardDescription" in tag :
					if tag["standardDescription"] == "aux power":
						print(tag["dataTagId"])
						taglist[tag["standardDescription"]] = [tag["dataTagId"]]
						columns_to_ffill.append(tag["standardDescription"])

	except Exception as e:
		print(e)
		print("auxillary power tag not found ")

	FormMeta = config["api"]["meta"] + '/forms?filter={"where":{"unitsId":"'+ unitId +'","name":"'+systemName+'"}}'
	FormMetares = requests.get(FormMeta)
	if FormMetares.status_code == 200 and len(FormMetares.json())!=0:
		FormMeta = FormMetares.json()[0]
		compiled_patterns = [re.compile(r'\b' + re.escape(pattern) + r'\b', re.IGNORECASE) for pattern in ConsiderationList]
		for tag in FormMeta["fields"]:
			for pattern in compiled_patterns:
				if "standardDescription" in tag:
					last_word = tag["standardDescription"].split()[-1]
					if last_word.isdigit():
						if re.search(pattern, tag["standardDescription"]) and tag.get("dataTagId"):
							taglist[tag["standardDescription"]] = [tag["dataTagId"]]
							columns_to_ffill.append(tag["standardDescription"])
	else:
		FormMetares = ""
	
	try:
		df=getHistoricValues(taglist,startTime, endTime)
		#forward fill and backfil for specific coal and cost columns since they are entered per day basis and we are fetching hourly basis 
		#hourly basis is fetched becoz coal flow per hour = steam flow of whole day/steamflow per hour is required

		df.dropna(subset=['boilerEfficiency','boilerSteamFlow'],inplace=True)
		columns_to_check = ['boilerEfficiency', 'boilerSteamFlow']
		# Drop rows where any of the specified columns have a value of 0
		df = df[~(df[columns_to_check] == 0).any(axis=1)]
		your_column_name = 'boilerEfficiency'  
		# df = df[df[your_column_name] >= 60]
		coalFlowcolumns = [col for col in df.columns if re.search(r"Coal Flow", col, re.IGNORECASE)]
		mask_not_all_nan = ~df[coalFlowcolumns].isna().all(axis=1)
		df.loc[mask_not_all_nan, coalFlowcolumns] = df.loc[mask_not_all_nan, coalFlowcolumns].fillna(0)
		df[columns_to_ffill] = df[columns_to_ffill].fillna(method='ffill')
		df[columns_to_ffill] = df[columns_to_ffill].fillna(method='bfill')
		df = df[df[your_column_name] >= 60]
		df.reset_index(drop=True, inplace=True)
		df['time'] = pd.to_datetime(df['time'],format='%d-%m-%Y %H:%M:%S')
		#THRESHOLD IS SET BECAUSE IN SOMECASE REALTIMEDATA ARE NOT PRESENT
		min_data_points_threshold = 24
		grouped_data = df.groupby(df['time'].dt.date)['boilerSteamFlow'].apply(lambda x: x.sum() if len(x) >= min_data_points_threshold else x.mean() * 24).reset_index()
		grouped_data.columns = ['Date', 'netBoilerSteamFlow']
		df = pd.merge(df, grouped_data, left_on=df['time'].dt.date, right_on='Date', how='left')
		df.drop(columns=['Date'], inplace=True)
		total_coal_flow = sum(fuel_data["Coal Flow"] for fuel_data in res["fuelData"])
		weighted_avg_coal_cost = sum((fuel_data["Coal Flow"] / total_coal_flow) * fuel_data["Coal Cost"] for fuel_data in res["fuelData"])
		print("Weighted Average Coal Cost:", weighted_avg_coal_cost)
		print("weighted coal average cost")

		#df wise calculation process  # hover using df.loc uses more memory as it creates a new df 
		coal_flow_columns = df.loc[:, df.columns.str.contains('coal\s*flow', case=False)& ~df.columns.str.contains(r'coalflow', case=False)]
		df["totalCoalFlow"] = coal_flow_columns.sum(axis=1)
		coal_cost_columns = df.loc[:, df.columns.str.contains('coal\s*cost', case=False)]
		df['totalFuelCost']=coal_cost_columns.sum(axis=1)
		df["weightedLandingCost"] = 0
		for flow_col, cost_col in zip(coal_flow_columns.columns, coal_cost_columns.columns):
			df["individual_costoffuel"]=(df[flow_col] / df["totalCoalFlow"]) * df[cost_col]
			df["weightedLandingCost"] += df["individual_costoffuel"]
		df.drop(columns=["individual_costoffuel"],inplace=True) 
		df['directCoalflow']=(df['totalCoalFlow']*df['boilerSteamFlow'])/df['netBoilerSteamFlow']
		df["directCostofFuel"]=df["weightedLandingCost"]* df['directCoalflow']
		df["directCostperunitSteam"]=(df['directCostofFuel'])/df['boilerSteamFlow']
		df.dropna(subset=['costPerUnitSteam','directCostofFuel','directCoalflow','directCostperunitSteam'],inplace=True)
		pattern = re.compile(r'coal flow \d+')
		for coal_column in coal_flow_columns:
			percentage_column = coal_column + '_percentage'
			displayList.append(coal_column + '_percentage')
			df[percentage_column] = df[coal_column] / df['totalCoalFlow'] * 100
		#APPENDING DIRECT COAL COLUMNS TO DISPLAYLIST FOR SHOWING IN ORDER
		displayList.append("directCoalflow")
		displayList.append("directCostofFuel")
		displayList.append("directCostperunitSteam")

		conditions = {}
		for index, data in enumerate(res["fuelData"], start=1):
			for key in list(data.keys()):
				if key != 'name':
					new_key = f"{key} {index}"
					data[new_key] = data.pop(key)
		#THIS LAST INTEGER SPLIT MUST BE FINE TUNED MORE 
		# for fuel_data in res["fuelData"]:
		#     last_integer = int(fuel_data["name"].split()[-1])
		#     for key in list(fuel_data.keys()):
		#         # print("coal cost names")
		#         # print("Coal Cost"+" " +str(last_integer))
		#         if key != "name":
		#             fuel_data[f"{key} {last_integer}"] = fuel_data.pop(key)
		refDict={}
		for fuel_data in res["fuelData"]:
			for fuel, value in fuel_data.items():
				if "name" not in fuel and not re.match(r'Coal\s*Cost\s*\d+', fuel):
					column_name = fuel.replace(" ", " ")
					if re.match(r'Coal\s*Flow\s*\d+', fuel):
						condition = f'df["{fuel}_percentage"] == {value}'
					else:
						condition = f'df["{fuel}"] == {value}'
					conditions.setdefault(column_name, []).append(condition)
				if re.match(r'Coal\s*Flow\s*\d+', fuel):
					refDict.update({f"{fuel}":value})
		ref_row = pd.Series({key+ '_percentage': value for key, value in refDict.items() if 'Coal Flow' in key})
		filtered_df = df.copy()
		for col, condition_list in conditions.items():
			combined_condition = ' & '.join(['(' + condition + ')' for condition in condition_list])
			filtered_df = filtered_df[eval(combined_condition)]
			# filtered_df = filtered_df.query(condition, local_dict={'df': df})
		if not filtered_df.empty:
			filtered_df.set_index('time', inplace=True)
			daily_df = filtered_df.resample('D').sum()
			daily_df.reset_index(inplace=True)
			sorted_df = daily_df.sort_values(by='costPerUnitSteam')
			unique_df = sorted_df.drop_duplicates(subset='costPerUnitSteam')
			topbesteconomics=unique_df.nsmallest(10, 'costPerUnitSteam').head(10)
			min_cost_row = unique_df.nsmallest(1, 'costPerUnitSteam').head(1)
			


		#REQUIRES CORRECTION BASED ON REQUIREMENT
		if filtered_df.empty or filtered_df is None:
			print("no matchinf columns finding close")
			conditions = {key+ '_percentage': value for key, value in conditions.items() if 'Coal Flow' in key}
			numeric_columns = list(conditions.keys()) 
			distances = np.sqrt(np.sum((df[numeric_columns] - ref_row)**2, axis=1))
			df['Distance'] = distances
			coal_keys_with_zero = []
			df_refined = pd.DataFrame()
			for coal, value in refDict.items():
				if "Coal Flow" in coal and value==0 :
					coal_keys_with_zero.append(coal)
			if len(coal_keys_with_zero) >=1:
				coalcheck = (df[coal_keys_with_zero] == 0).all(axis=1)
				df_refined = df[coalcheck]
				if df_refined.empty or df_refined is None:
					print("though coal comb is 0 refined is empty in certain cases")
					df_refined = df.sort_values(by='Distance')
				else:
					df_refined = df_refined.sort_values(by='Distance')
				# min_cost_row = df.nsmallest(1, 'costPerUnitSteam').head(1)
				df.set_index('time', inplace=True)
				daily_df = df.resample('D').mean()
				daily_df.reset_index(inplace=True)
				sorted_df = daily_df.sort_values(by='costPerUnitSteam')
				unique_df = sorted_df.drop_duplicates(subset='costPerUnitSteam')
				topbesteconomics=unique_df.nsmallest(10, 'costPerUnitSteam').head(10)
				min_cost_row = unique_df.nsmallest(1, 'costPerUnitSteam').head(1)
			if df_refined.empty or df_refined is None:
				df_refined = df.sort_values(by='Distance')
				min_cost_row = df.nsmallest(1, 'costPerUnitSteam').head(1)
				df.set_index('time', inplace=True)
				daily_df = df.resample('D').mean()
				daily_df.reset_index(inplace=True)
				sorted_df = daily_df.sort_values(by='costPerUnitSteam')
				unique_df = sorted_df.drop_duplicates(subset='costPerUnitSteam')
				topbesteconomics=unique_df.nsmallest(10, 'costPerUnitSteam').head(10)
				min_cost_row = unique_df.nsmallest(1, 'costPerUnitSteam').head(1)
			# df_sorted = df.sort_values(by='Distance')
			filtered_df=df_refined.head(20).copy()
			filtered_df.drop(columns=['Distance'], inplace=True)

	# min_cost_row = filtered_df.nsmallest(1, 'costPerUnitSteam').head(1)
		min_cost_row.reset_index(drop=True)
		min_cost_row['time'] =min_cost_row['time'].dt.strftime('%d-%m-%Y %H:%M:%S')
		min_cost_row["correctedcostPerUnitSteam"] = (weighted_avg_coal_cost* min_cost_row['directCoalflow'])/min_cost_row['boilerSteamFlow']
		min_cost_row =min_cost_row.to_dict(orient='records')
		formatted_data = []
		min_cost_row=min_cost_row[0]
		for key, value in min_cost_row.items():
			formatted_value = str(round(value, 2)) if isinstance(value, float) else str(value)
			item = {"name": key, "value": formatted_value, "type": "", "unit": ""}
			if key == 'costPerUnitSteam':
				print("yes key matches")
				item["name"] = 'IndirectCostPerUnitSteam'
			if key.lower() == 'time':
				formatted_data.append({"name": key, "value": value, "type": "Date", "unit": ""})
			for pattern, type_info in pattern_types.items():
				if re.match(pattern, key, re.IGNORECASE):
					item['type'] = type_info["type"]
					item['unit'] = type_info["unit"]
					formatted_data.append(item)
					break
		topbesteconomics.drop(columns=['Distance'], inplace=True)
		topbesteconomics=process_dataframe(topbesteconomics, weighted_avg_coal_cost, displayList)
		data_values=process_dataframe(filtered_df, weighted_avg_coal_cost, displayList)
	except Exception as e:
		print("exception selected tags dont have values in timeperiod " , e)
		df = pd.DataFrame(columns=df.columns)
		columns = df.columns.tolist()
		data_values = [columns] + df.values.tolist()
		topbesteconomics= data_values
		data_values=data_values
		formatted_data= [{"name":"time","value":"0","type":"Date","unit":""},{"name":"IndirectCostPerUnitSteam","value":"0","type":"costPerUnitSteam","unit":"Rs/ton"},{"name":"boilerEfficiency","value":"0","type":"boilerEfficiency","unit":"%"},{"name":"aux power","value":"0","type":"aux power","unit":"mW"},{"name":"directCostperunitSteam","value":"0","type":"costPerUnitSteam","unit":"Rs/ton"},{"name":"Coal Flow 1_percentage","value":"0","type":"fuelratios","unit":"%"},{"name":"Coal Flow 2_percentage","value":"0","type":"fuelratios","unit":"%"},{"name":"Coal Flow 3_percentage","value":"0","type":"fuelratios","unit":"%"},{"name":"correctedcostPerUnitSteam","value":"0","type":"costPerUnitSteam","unit":"Rs/ton"}]

	# filtered_df.reset_index(drop=True, inplace=True)
	# filtered_df['time'] =filtered_df['time'].dt.strftime('%d-%m-%Y %H:%M:%S')

	# filtered_df["NetTgLoad"]= (filtered_df["TgLoad"]-(filtered_df["aux power"]/24))
	# # filtered_df["DirectCost/KWh"]= (filtered_df["weightedLandingCost"]*filtered_df["directCoalflow"])/(filtered_df["TgLoad"]*1000)
	# # filtered_df["NetDirectCost/KWh"]= (filtered_df["weightedLandingCost"]*filtered_df["directCoalflow"])/(filtered_df["NetTgLoad"]*1000)
	# # filtered_df["InDirectCost/KWh"]= (filtered_df["weightedLandingCost"]*filtered_df["coalFlow"])/(filtered_df["TgLoad"]*1000)
	# # filtered_df["NetInDirectCost/KWh"]= (filtered_df["weightedLandingCost"]*filtered_df["coalFlow"])/(filtered_df["NetTgLoad"]*1000)
	# # # filtered_df["Correctedcostoffuel"]=weighted_avg_coal_cost* filtered_df['directCoalflow']
	# filtered_df["correctedSteamCost"] = (weighted_avg_coal_cost* filtered_df['directCoalflow'])/filtered_df['boilerSteamFlow']
	# filtered_df["correctedDirectCost/KWh"]= (weighted_avg_coal_cost*filtered_df["directCoalflow"])/(filtered_df["TgLoad"]*1000)
	# filtered_df["correctedNetDirectCost/KWh"]= (weighted_avg_coal_cost*filtered_df["directCoalflow"])/(filtered_df["NetTgLoad"]*1000)
	# filtered_df["correctedInDirectCost/KWh"]= (weighted_avg_coal_cost*filtered_df["coalFlow"])/(filtered_df["TgLoad"]*1000)
	# filtered_df["correctedNetInDirectCost/KWh"]= (weighted_avg_coal_cost*filtered_df["coalFlow"])/(filtered_df["NetTgLoad"]*1000)

	# filtered_df['time'] = filtered_df['time'].astype(str)
	# filtered_df.rename(columns={'time': 'Date'}, inplace=True)
	# columns_to_round = [col for col in filtered_df.columns if col != 'time']
	# filtered_df[columns_to_round] = filtered_df[columns_to_round].round(2)
	# remaining_columns = [col for col in filtered_df.columns if col not in displayList]
	# new_columns_order = displayList + remaining_columns
	# df_reordered = filtered_df[new_columns_order]
	# prefix = 'inDirect'
	# columns_to_check = ['coalFlow', 'costOfFuel', 'costPerUnitSteam']
	# column_mapping = {col: prefix + col if col in columns_to_check else col for col in df_reordered.columns}
	# changed_columns = [new_col for col, new_col in column_mapping.items() if new_col != col]
	# displayList.extend(changed_columns)
	# df_reordered.rename(columns=column_mapping, inplace=True)
	# pd.set_option('display.max_columns',None)
	# print("reordered df")
	# # print(df_reordered)
	# columns = df_reordered.columns.tolist() 
	# data_values = [columns] + df_reordered.values.tolist()
	json_data = json.dumps({"bestachieved":formatted_data,"data": data_values,"boilereconomics":topbesteconomics, "config":resultdict}, separators=(',', ':'))
	# json_data = json.dumps({"bestachieved":formatted_data,"data": data_values, "config":resultdict}, separators=(',', ':'))
	return json_data


if __name__ == '__main__':
	app.run(host= '0.0.0.0', threaded=True, port=5068, debug=True)#production
	# app.run(host= '0.0.0.0', threaded=True, port=5077, debug=False)
# if __name__ == "__main__":
#      app.run(threaded=True,  debug=False)
