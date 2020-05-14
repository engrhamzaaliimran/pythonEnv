# DATABASE VARIABLES SET BY USER
DATABASE_USER = "dd"
DATABASE_PASSWD = "dd"
DATABASE_HOST = "192.168.2.214"
# DATABASE_USER = "root"
# DATABASE_PASSWD = ""
# DATABASE_HOST = "localhost"
DATABASE_NAME = "qor"
UPLOAD_IMG_API_URL = "http://127.0.0.1:5000/upload-image"

import sys,os,subprocess
import argparse
import logging
from datetime import datetime, timedelta
import math
import csv
import operator
import configparser
import sqlalchemy as db
import MySQLdb
import pandas as pd
from enum import Enum
from collections import OrderedDict 
import requests

CHECKER_PATH=""
FERMI_PATH=""
LOGGER = ""
PARITION_SIZE = 50000

# Using enumerate for the enteries in AnalysisName Table as statisticalAnalysisNames, geometricalAnalysisNames and runtimeAnalysisNames
class statisticalAnalysisNames(Enum):
    EPE_target_vs_Max_PV_Contour = 1
    EPE_target_vs_Min_PV_Contour = 2
    EPE_target_vs_Nominal_mask_simulation_f0d0 = 3
    EPE_target_vs_mask_simulation_fn2d0 = 4
    EPE_target_vs_mask_simulation_fp2d0 = 5
    EPE_target_vs_mask_simulation_f0dn = 6
    EPE_target_vs_mask_simulation_f0dp = 7
    Width_of_PV_band = 8
    Width_of_Simple_Meef_band = 9

class geometricalAnalysisNames(Enum):
    MRC_Area = 10
    MRC_Spacing = 11
    MRC_width = 12

class runtimeAnalysisNames(Enum):
    Target_Prep_Runtime = 13
    CTM_fg = 14
    CTM_exec_time = 15
    QTM_fg = 16
    QTM_exec_time = 17
    PostProcess_exec_time = 18
    Total_Fermi_Runtime = 19
    The_checker_runtime = 20


# dict for statistical analysis
statical_analysis_dict={"EPE_target_vs_Max_PV_Contour":("maxpvepe","3:1"),
                    "EPE_target_vs_Min_PV_Contour":("minpvepe","3:2"),
                    "EPE_target_vs_Nominal_mask_simulation_f0d0":("epenompc","3:3"),
                    "EPE_target_vs_mask_simulation_fn2d0":("epepcfn2d0","3:4"),
                    "EPE_target_vs_mask_simulation_fp2d0":("epepcfp2d0","3:5"),
                    "EPE_target_vs_mask_simulation_f0dn":("epepcf0dn","3:6"),
                    "EPE_target_vs_mask_simulation_f0dp":("epepcf0dp","3:7"),
                    "Width_of_PV_band":("pvwidth","1:0"),
                    "Width_of_Simple_Meef_band":("meefwidth","4:0")}


''' This function enter the data into database, 
it takes location of test directory and multiple ids in list, 
Database related values set at top of database '''
def enteringDataIntoDatabase(_path, _list_ids, _force_flag, _cron_flag):
    global CHECKER_PATH, LOGGER

    # checking, if the essential data is present in ini file.
    def checkEssentialData():
        if not config.has_section("Main_Stats"):
            LOGGER.error("ERROR: Main_Stats section not found.")
            return False
        else:
            if not config.has_option("Main_Stats", "run_date_time"):
                LOGGER.error("ERROR: run_date_time not found in section Main_Stats.")
                return False
            elif config["Main_Stats"]["run_date_time"] == "None":
                LOGGER.error("ERROR: run_date_time is None in section Main_Stats.")
                return False
            if not config.has_option("Main_Stats", "fermi_job_name"):
                LOGGER.error("ERROR: fermi_job_name not found in section Main_Stats.")
                return False
            elif config["Main_Stats"]["fermi_job_name"] == "None":
                LOGGER.error("ERROR: fermi_job_name is None in section Main_Stats.")
                return False
            if not config.has_option("Main_Stats", "fermi_id"):
                LOGGER.error("ERROR: fermi_id not found in section Main_Stats.")
                return False
            elif config["Main_Stats"]["fermi_id"] == "None":
                LOGGER.error("ERROR: fermi_id is None in section Main_Stats.")
                return False
            if not config.has_option("Main_Stats", "checker_id"):
                LOGGER.error("ERROR: checker_id not found in section Main_Stats.")
                return False
            elif config["Main_Stats"]["checker_id"] == "None":
                LOGGER.error("ERROR: checker_id is None in section Main_Stats.")
                return False
        return True
    
    # checking the validation of keys in the sections of ini file.
    def checkDataValidation(section, key):
        if config.has_option(section, key):
            if config[section][key] == "None":
                LOGGER.info("INFO: "+key+" found in section "+section+".")
                return None
            LOGGER.info("INFO: "+key+" found in section "+section+".")
            return config[section][key]
        else:
            LOGGER.error("ERROR: "+key+" not found in section "+section+".")
            return None
    
    # checking the existance of section in ini file.
    def checkSectionExist(section):
        if not config.has_section(section):
            LOGGER.error("ERROR: "+section+" section not found.")
            return False
        else:
            return True

    # This function take half image_name as input and find in directory and return image_path or None
    def getExactImagePath(_image_name,_run_id):
        for file in os.listdir(CHECKER_PATH + "/qor/asset"):
            if _image_name in file:
                return str(_run_id)+"/"+os.path.basename(file)
                LOGGER.info("INFO: "+file+" image found in qor/asset directory" )
        return None

    #Configure collective parser log that contain one liner for all entered ids 
    record_main_logger = logging.getLogger("collective_record_logger")
    record_main_logger.setLevel(logging.DEBUG)
    debug_log = logging.FileHandler(os.path.join(os.getcwd(), "record.log"), mode="w")
    debug_log.setLevel(logging.INFO)
    record_main_logger.addHandler(debug_log)

    # makeing connection to database.
    database_connection_str = "mysql+mysqldb://%s:%s@%s/%s" %(DATABASE_USER,DATABASE_PASSWD,DATABASE_HOST,DATABASE_NAME)
    engine = db.create_engine(database_connection_str)
    connection = engine.connect()
    metadata = db.MetaData()

    # Initiallizing all the tables as in database.
    Run = db.Table("Run", metadata, autoload=True, autoload_with=engine)
    Machine = db.Table("Machine", metadata, autoload=True, autoload_with=engine)
    FermiModel = db.Table("FermiModel", metadata, autoload=True, autoload_with=engine)
    Revision = db.Table("Revision", metadata, autoload=True, autoload_with=engine)
    Test = db.Table("Test", metadata, autoload=True, autoload_with=engine)
    AnalysisName = db.Table("AnalysisName", metadata, autoload=True, autoload_with=engine)
    StatisticalAnalysis = db.Table("StatisticalAnalysis", metadata, autoload=True, autoload_with=engine)
    GeometricalAnalysis = db.Table("GeometricalAnalysis", metadata, autoload=True, autoload_with=engine)
    RuntimeAnalysis = db.Table("RuntimeAnalysis", metadata, autoload=True, autoload_with=engine)

    # Open Fermi QOR File contains all recorded test directory path with their last modified time
    _FERMI_QOR_FILE = os.path.expanduser("~") + "/.fermi_qor"
    if not os.path.isfile(_FERMI_QOR_FILE):
        fermi_qor_fd = open(_FERMI_QOR_FILE,"w+")
        fermi_qor_fd.write("Directory_Path,Modified_Time\n")
        fermi_qor_fd.close()

    latest_test_time = 0
    for id_num in _list_ids:
        CHECKER_PATH=os.path.normpath(_path+"/"+str(id_num))
        
        checker_id=str(id_num)
        if not os.path.isdir(CHECKER_PATH):
            record_main_logger.info(str(id_num)+":: ERROR:Directory with JOB_ID:"+str(id_num)+" doesnot exist in "+_path)
            continue
        elif not os.path.isdir(CHECKER_PATH+"/qor"):
            record_main_logger.info(str(id_num)+":: ERROR:qor directory in "+CHECKER_PATH+" doesnot exist")
            continue

        # qor directory creation in checker directory
        os.system("mkdir -p "+CHECKER_PATH+"/qor/logs/record_log")

        # Configuring logging
        LOGGER=logging.getLogger("individual_record_logger")
        LOGGER.setLevel(logging.DEBUG)
        # to log debug messages                               
        debug_log = logging.FileHandler(CHECKER_PATH+"/qor/logs/record_log/info.log")
        
        debug_log.setLevel(logging.INFO)
        # to log errors messages
        error_log = logging.FileHandler(CHECKER_PATH+"/qor/logs/record_log/error.log")
        error_log.setLevel(logging.ERROR)
        LOGGER.addHandler(debug_log)
        LOGGER.addHandler(error_log)

        LOGGER.info("INFO: "+CHECKER_PATH + " found")
        if not os.path.isfile(CHECKER_PATH+"/qor/Fermi_stats.txt"):
            LOGGER.error("ERROR: Fermi_stats.txt not found in "+CHECKER_PATH+"/qor")
            record_main_logger = logging.getLogger("collective_record_logger")
            record_main_logger.info(str(id_num)+":: ERROR:Fermi_stats.txt not found in "+CHECKER_PATH+"/qor")
            continue

        # Reading .ini files 
        config = configparser.ConfigParser()
        config.read(CHECKER_PATH+"/qor/Fermi_stats.txt")

        if not checkEssentialData():
            record_main_logger = logging.getLogger("collective_record_logger")
            record_main_logger.info(str(id_num)+":: ERROR:EsstentialData not present in Fermi_stats file")
            continue

        checker_modified_time = os.path.getmtime(CHECKER_PATH)
        checker_modified_time = datetime.utcfromtimestamp(checker_modified_time).strftime('%Y-%m-%d %H:%M:%S')

        print("\ni am here")
        # Read fermi_qor_file at home directory
        fermi_qor_fd = pd.read_csv(_FERMI_QOR_FILE,delimiter=",")
        directory_names = list(fermi_qor_fd["Directory_Path"])
        if CHECKER_PATH in directory_names:
            row_idx = directory_names.index(CHECKER_PATH)
            if str(fermi_qor_fd["Modified_Time"][row_idx]) == checker_modified_time:
                print("FILE")
                LOGGER.info("INFO: Already updated in database, record_flag set in fermi_record_flag_file")
                record_main_logger = logging.getLogger("collective_record_logger")
                record_main_logger.info(str(id_num)+":: Already updated in database, record_flag set")
                continue

        # Inserting data in database for Machine table.
        user_name = checkDataValidation("Main_Stats","user")
        machine_name = checkDataValidation("Main_Stats","machine_name")
        query = db.select([Machine.columns.id]).where(db.and_(Machine.columns.user_name == user_name, Machine.columns.machine_name == machine_name ))
        results = connection.execute(query).fetchall()

        # if results:
        #     last_cron_update = results[0][1]
        #     if last_cron_update and not _force_flag and checker_modified_time < str(last_cron_update):
        #         print("CRON")
        #         LOGGER.info("INFO: Already updated in database, last_cron_time is greater than checker modified time")
        #         record_main_logger = logging.getLogger("collective_record_logger")
        #         record_main_logger.info(str(id_num)+":: Already updated in database, time is less than last modified time")
        #         continue
        
        if results:
            user_id=results[0][0]
        else:
            query = db.insert(Machine).values(user_name=user_name, machine_name=machine_name) 
            result_proxy = connection.execute(query)
            user_id = (result_proxy.inserted_primary_key)[0]

        # Inserting data in database for FermiModel table.
        tmod_name = checkDataValidation("Main_Stats","tmod_name")
        process_condition = checkDataValidation("Main_Stats","process_condition")
        query = db.select([FermiModel.columns.id]).where(db.and_(FermiModel.columns.tmod_name == tmod_name, FermiModel.columns.process_condition == process_condition ))
        results = connection.execute(query).fetchall()
        if results:
            model_id=results[0][0]
        else:
            query = db.insert(FermiModel).values(tmod_name=tmod_name, process_condition=process_condition) 
            result_proxy = connection.execute(query)
            model_id = (result_proxy.inserted_primary_key)[0]

        # Inserting data in database for Revision table.
        commit = checkDataValidation("Main_Stats","revision_commit")
        query = db.select([Revision.columns.id]).where(Revision.columns.commit == commit )
        results = connection.execute(query).fetchall()
        if results:
            revision_id=results[0][0]
        else:
            query = db.insert(Revision).values(commit=commit, date=checkDataValidation("Main_Stats","revision_date"), branch=checkDataValidation("Main_Stats","revision_branch")) 
            result_proxy = connection.execute(query)
            revision_id = (result_proxy.inserted_primary_key)[0]

        # Inserting data in database for Test table.
        name = checkDataValidation("Main_Stats","name")
        query = db.select([Test.columns.id]).where(Test.columns.name == name )
        results = connection.execute(query).fetchall()
        if results:
            test_id=results[0][0]
        else:
            query = db.insert(Test).values(name=name)
            result_proxy = connection.execute(query)
            test_id = (result_proxy.inserted_primary_key)[0]


        # Implementing the funtionality of baseline in Run table.
        fermi_job_name = checkDataValidation("Main_Stats","fermi_job_name")
        run_date_time = checkDataValidation("Main_Stats","run_date_time")
        query = db.select([db.func.max(Run.columns.run_date_time)]).where(Run.columns.fermi_job_name == fermi_job_name )
        results = connection.execute(query).fetchall()
        result = [str(r) for (r,) in results]
        is_baseline = False
        if (result[0] != "None"):
            old_datetime_entry = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S.%f")
            new_datetime_entry = datetime.strptime(run_date_time, "%Y-%m-%d %H:%M:%S.%f")
            if (new_datetime_entry > old_datetime_entry):
                query = db.update(Run).values(is_baseline = False).where(db.and_(Run.columns.run_date_time == old_datetime_entry, Run.columns.fermi_job_name == fermi_job_name))
                results = connection.execute(query)
                is_baseline = True
        else:
            is_baseline = True

        # Inserting data in database for Run table.
        query = db.insert(Run).values(run_date_time=run_date_time, fermi_job_name=fermi_job_name, fermi_job_id=checkDataValidation("Main_Stats","fermi_id"),
                                    checker_id=checkDataValidation("Main_Stats","checker_id"), user_id=user_id, model_id=model_id, revision_id=revision_id,
                                    test_id=test_id, is_baseline=is_baseline, epe_1d=checkDataValidation("Main_Stats","epe_1d"), 
                                    epe_2d=checkDataValidation("Main_Stats","epe_2d"), total_errors=checkDataValidation("Main_Stats","total_errors"),
                                    max_err_per_partition=checkDataValidation("Main_Stats","max_err_per_partion"), grid=checkDataValidation("Main_Stats","grid"),
                                    gpu=checkDataValidation("Main_Stats","gpu"), iterations=checkDataValidation("Main_Stats","optimizer_iterations"),
                                    partition=checkDataValidation("Main_Stats","partition"), expect_run_time_50_gpu=checkDataValidation("Main_Stats","expect_run_time_50_gpu"),
                                    expect_run_time_1_gpu=checkDataValidation("Main_Stats","expect_run_time_1_gpu"), design_size=checkDataValidation("Main_Stats","design_size"),
                                    mask_file_size=checkDataValidation("Main_Stats","mask_file_size")) 
        
        result_proxy = connection.execute(query)
        run_id = (result_proxy.inserted_primary_key)[0]

        # Inserting data in database for StatisticalAnalysis table.
        values_list = []
        for entry in statisticalAnalysisNames:
            stat_section_name="Statistical_Analysis:%s" % entry.name
            if checkSectionExist(stat_section_name):
                if not config.has_option(stat_section_name, "avalibility"):
                    graph_path = getExactImagePath(entry.name, run_id)
                    clip_path = getExactImagePath(statical_analysis_dict[entry.name][0],run_id)
                    values_list.append({"run_id":run_id, "analysis_type":entry.value, "graph": graph_path, "min":checkDataValidation(stat_section_name,"min"),
                                        "10th":checkDataValidation(stat_section_name,"10th"), "25th":checkDataValidation(stat_section_name,"25th"), 
                                        "50th":checkDataValidation(stat_section_name,"50th"), "75th":checkDataValidation(stat_section_name,"75th"), 
                                        "90th":checkDataValidation(stat_section_name,"90th"), "max":checkDataValidation(stat_section_name,"max"), 
                                        "clips":clip_path, "marker_x":checkDataValidation(stat_section_name,"marker_x"), 
                                        "marker_y":checkDataValidation(stat_section_name,"marker_y")})

        query = db.insert(StatisticalAnalysis)
        result_proxy = connection.execute(query,values_list)

        # Inserting data in database for GeometricalAnalysis table.
        if checkSectionExist("Geometric_Analysis_Stats"):
            mrc_area_count = checkDataValidation("Geometric_Analysis_Stats","mrc_area_count")
            mrc_spacing_count = checkDataValidation("Geometric_Analysis_Stats","mrc_spacing_count")
            mrc_width_count = checkDataValidation("mrc","mrc_width_count")
            mrc_area_clip_path = getExactImagePath("mrc_9_0",run_id)
            mrc_width_clip_path = getExactImagePath("mrc_9_1",run_id)
            mrc_spacing_clip_path = getExactImagePath("mrc_9_2",run_id)
            
            
            query = db.insert(GeometricalAnalysis)
            values_list = [ {"run_id":run_id, "analysis_type":geometricalAnalysisNames.MRC_Area.value, "count":mrc_area_count,"max":checkDataValidation("Geometric_Analysis_Stats","mrc_area_min_max_value"),"clip":mrc_area_clip_path,"marker_x":checkDataValidation("Geometric_Analysis_Stats","mrc_area_marker_x"),"marker_y":checkDataValidation("Geometric_Analysis_Stats","mrc_area_marker_y") },
                            {"run_id":run_id, "analysis_type":geometricalAnalysisNames.MRC_Spacing.value, "count":mrc_spacing_count,"max":checkDataValidation("Geometric_Analysis_Stats","mrc_spacing_min_max_value"),"clip":mrc_spacing_clip_path,"marker_x":checkDataValidation("Geometric_Analysis_Stats","mrc_spacing_marker_x"),"marker_y":checkDataValidation("Geometric_Analysis_Stats","mrc_spacing_marker_y")},
                            {"run_id":run_id, "analysis_type":geometricalAnalysisNames.MRC_width.value, "count":mrc_width_count,"max":checkDataValidation("Geometric_Analysis_Stats","mrc_width_min_max_value"),"clip":mrc_width_clip_path,"marker_x":checkDataValidation("Geometric_Analysis_Stats","mrc_width_marker_x"),"marker_y":checkDataValidation("Geometric_Analysis_Stats","mrc_width_marker_y")} ]

            result_proxy = connection.execute(query,values_list)

        # Inserting data in database for RuntimeAnalysis table.
        if checkSectionExist("Runtime_Analysis_Stats"):
            values_list = [ {"run_id":run_id, "analysis_type":runtimeAnalysisNames.Target_Prep_Runtime.value, "run_time":checkDataValidation("Runtime_Analysis_Stats","target_prep_runtime") },
                            {"run_id":run_id, "analysis_type":runtimeAnalysisNames.CTM_fg.value, "run_time":checkDataValidation("Runtime_Analysis_Stats","ctm_fg")  },
                            {"run_id":run_id, "analysis_type":runtimeAnalysisNames.CTM_exec_time.value, "run_time":checkDataValidation("Runtime_Analysis_Stats","ctm_exec_time")  },
                            {"run_id":run_id, "analysis_type":runtimeAnalysisNames.QTM_fg.value, "run_time":checkDataValidation("Runtime_Analysis_Stats","qtm_fg") },
                            {"run_id":run_id, "analysis_type":runtimeAnalysisNames.QTM_exec_time.value, "run_time":checkDataValidation("Runtime_Analysis_Stats","qtm_exec_time") },
                            {"run_id":run_id, "analysis_type":runtimeAnalysisNames.PostProcess_exec_time.value, "run_time":checkDataValidation("Runtime_Analysis_Stats","postprocess_exec_time") },
                            {"run_id":run_id, "analysis_type":runtimeAnalysisNames.Total_Fermi_Runtime.value, "run_time":checkDataValidation("Runtime_Analysis_Stats","total_fermi_runtime") },
                            {"run_id":run_id, "analysis_type":runtimeAnalysisNames.The_checker_runtime.value, "run_time":checkDataValidation("Runtime_Analysis_Stats","the_checker_runtime") } ]
            
            query = db.insert(RuntimeAnalysis)
            result_proxy = connection.execute(query,values_list)

        # Uploading all images to Server using API
        # images = set({})
        # for file in os.listdir(CHECKER_PATH+"/qor/asset"):
        #     if ".png" in file:
        #         fd_image = open(CHECKER_PATH+"/qor/asset/"+file,'rb')
        #         images.add(('image',fd_image))
        #         LOGGER.info("INFO: Add "+os.path.basename(file)+" in sending API images set")
        # if images:
        #     response = requests.post(UPLOAD_IMG_API_URL+"/"+str(run_id), files = images)
        #     if response.status_code == 200:
        #         LOGGER.info("INFO: Successfully transfer images to server using APIs")
        #     else:
        #         LOGGER.error("ERROR: API call failed with error code:"+str(response.status_code))

        # If one directory has multiple machines run therefore update last_update of each job id
        # Compare job id last update time with last_cron_time and update database with latest time 
        # if _cron_flag:
        #     query = db.select([Machine.columns.last_cron_update]).where(db.and_(Machine.columns.user_name == user_name, Machine.columns.machine_name == machine_name ))
        #     db_last_update_time = connection.execute(query).fetchall()[0][0]
        #     if db_last_update_time == None or checker_modified_time > str(db_last_update_time):
        #         query = db.update(Machine).values(last_cron_update = checker_modified_time)
        #         query = query.where(db.and_(Machine.columns.user_name == user_name, Machine.columns.machine_name == machine_name ))
        #         results = connection.execute(query)
        #         latest_test_time = checker_modified_time
        #         LOGGER.info("INFO: Update last modified time to database")

        # Write to fermi qor file
        fermi_qor_fd = open(_FERMI_QOR_FILE,"a")
        fermi_qor_fd.write(CHECKER_PATH+","+str(checker_modified_time)+"\n")
        fermi_qor_fd.close()


        record_main_logger = logging.getLogger("collective_record_logger")
        record_main_logger.info(str(id_num)+":: Successfully record")


''' This function takes and parse data from test directory, and create Fermi_stats.txt file.
It take location and list_ids as input parameter  '''
def parsingData(_path, _list_ids):
    # Check if the flow is checker or fermi.
    def checkFlow():
        cmd="grep flow= "+CHECKER_PATH+"/input/d2sflow.ini | cut -d = -f2"
        file=os.popen(cmd)
        flow=file.read()
        flow=flow.rstrip()
        return flow

    # Checks if value if empty, writes in logs in either case
    def checkValueExistence(value,key):
        if str(value) == "":
            LOGGER.error("ERROR: "+key+" not found.")
            return "None"
        else:
            LOGGER.info("INFO: "+key+" found ("+str(value)+").")
            return value

    # Finds and returns fermi id from custom_checks.args
    def getFermiId():
        if not os.path.isfile(CHECKER_PATH+"/input/custom_checks.args"):
            return -1
        else:
            cmd="grep input_design "+CHECKER_PATH+"/input/custom_checks.args"
            file=os.popen(cmd)
            fermi_id=file.read()
            fermi_id=fermi_id.split("/")
            fermi_id=fermi_id[len(fermi_id)-3]
        return fermi_id

    # Create TCL Script
    def creatingTMDSscript(type,layer,description,x,y):
        if "mrc" in type:
            script_name = "mrc_clips.tcl"
        else:
            script_name = "epe_clips.tcl"
        
        fd_tcl = ""
        if not os.path.isfile(CHECKER_PATH+"/qor/script/"+script_name):
            fd_tcl = open(CHECKER_PATH+"/qor/script/"+script_name,"w+")
            output_target_path = ""
            for file in os.listdir(FERMI_PATH + "/output"):
                if file.endswith(".target.oas"):
                    output_target_path = file
                    break
            output_mask_path = output_target_path.replace(".target","")

            fd_tcl.write("#Load in the checker output oasis file \n")
            fd_tcl.write("import caddatasource %s/output/output.oas\n" %CHECKER_PATH)
            fd_tcl.write("# Load in the mask input oasis file\n")
            fd_tcl.write("caddata current mask\n")
            fd_tcl.write("import caddatasource %s/output/%s\n" %(FERMI_PATH,output_mask_path))
            fd_tcl.write("palette dashed mask 1:1 0 \n")
            fd_tcl.write("palette stipple mask 1:1 0 \n")
            if "mrc" in type:
                input_oasis_path = ""
                for file in os.listdir(FERMI_PATH + "/input"):
                    if file.endswith(".oas"):
                        input_oasis_path = file
                        break
                fd_tcl.write("# Load in the input oasis file \n")
                fd_tcl.write("caddata current input \n")
                fd_tcl.write("import caddatasource %s/input/%s\n" %(FERMI_PATH,input_oasis_path))
            else:
                fd_tcl.write("# Load in the target input oasis file \n")
                fd_tcl.write("caddata current target \n")
                fd_tcl.write("import caddatasource %s/output/%s\n" %(FERMI_PATH,output_target_path))
            fd_tcl.write("palette dashed target 1:1 0 \n")
            fd_tcl.write("palette stipple target 1:1 0 \n")
            fd_tcl.write("palette edgecolor target 1:1 0 0 1 \n")
            fd_tcl.write("# For removing any error, occured in first screenshot \n")
            fd_tcl.write("view bbox 0 0 300 300 \n")
            fd_tcl.write("view snapshot dummy.png \n")
        else:
            fd_tcl = open(CHECKER_PATH+"/qor/script/"+script_name,"a")
        
        fd_tcl.write("\n \n \n")
        fd_tcl.write("#-----For %s has %s\n" %(description,layer))
        fd_tcl.write("# show %s \n" %description)
        fd_tcl.write("palette hide caddata 0:0 \n")
        fd_tcl.write("palette hide caddata 0:1 \n")
        fd_tcl.write("palette hide caddata 0:2 \n")
        fd_tcl.write("palette hide caddata 0:3 \n")
        fd_tcl.write("palette hide caddata 0:4 \n")
        fd_tcl.write("palette hide caddata 0:5 \n")
        fd_tcl.write("palette hide caddata 0:6 \n")
        fd_tcl.write("palette hide caddata 0:7 \n")
        fd_tcl.write("palette hide caddata 1:0 \n")
        fd_tcl.write("palette hide caddata 1:1 \n")
        fd_tcl.write("palette hide caddata 1:2 \n")
        fd_tcl.write("palette hide caddata 1:3 \n")
        fd_tcl.write("palette hide caddata 3:1 \n")
        fd_tcl.write("palette hide caddata 3:2 \n")
        fd_tcl.write("palette hide caddata 3:4 \n")
        fd_tcl.write("palette hide caddata 3:5 \n")
        fd_tcl.write("palette hide caddata 3:6 \n")
        fd_tcl.write("palette hide caddata 3:7 \n")
        fd_tcl.write("palette hide caddata 4:0 \n")
        fd_tcl.write("palette hide caddata 4:1 \n")
        fd_tcl.write("palette hide caddata 4:2 \n")
        fd_tcl.write("palette hide caddata 4:3 \n")
        fd_tcl.write("palette hide caddata 9:0 \n")
        fd_tcl.write("palette hide caddata 9:1 \n")
        fd_tcl.write("palette hide caddata 9:2 \n")
        fd_tcl.write("# Remove any previous markers \n")
        fd_tcl.write("marker clear * \n")
        fd_tcl.write("# turn on error marker \n")
        fd_tcl.write("palette show caddata %s \n" %layer)
        fd_tcl.write("palette stipple caddata %s 8 \n" %layer)
        fd_tcl.write("palette edgecolor caddata %s 1 0 1 \n" %layer)
        fd_tcl.write("palette fillcolor caddata %s 1 0 1 \n" %layer)
        fd_tcl.write("# Zoom in to the error location and take snap shot. \n") 
        fd_tcl.write("view bbox %f %f %f %f \n" %((x-150),(y-150),(x+150),(y+150)))
        fd_tcl.write("view center %f %f \n" %(x,y))
        fd_tcl.write("marker create %f %f \n" %(x,y))
        error_layers = layer.split(":")
        img_file_name = "%s_%s_%s.png" %(type,error_layers[0],error_layers[1])
        fd_tcl.write("view snapshot %s/qor/asset/%s \n" %(CHECKER_PATH,img_file_name))
        LOGGER.info("INFO: Write "+type+ " screenshots lines to "+script_name+" \n")
        
        # file.write("exit \n")
        fd_tcl.close()


    # Calculates and returns statistical analysis stats in the form of a dictionary
    def getStatisticalAnalysisStats(analysis_type):

        if analysis_type not in statical_analysis_dict:
            LOGGER.error("ERROR: Wrong argument passed to getStatisticalAnalysisStats")
            return -1
        else:
            LOGGER.info("INFO: Calculating statistical analysis stats for "+ analysis_type)
            analysis_name=statical_analysis_dict[analysis_type][0]
            
            
        files_in_checker_dir=os.listdir(CHECKER_PATH)
        num_of_files=len(files_in_checker_dir)
        filecnt=0
        statistical_stats={}
        values=[]
        sortedlist=[]
        worst_value = 0
        worst_x = 0
        worst_y = 0
        values = []
        for i in range(0,num_of_files):
            if analysis_name in files_in_checker_dir[i]:
                print(files_in_checker_dir[i])
                filecnt=filecnt+1
                # fh=open(CHECKER_PATH+"/"+files_in_checker_dir[i])
                # csv_reader = csv.reader(fh, delimiter=',')
                # readers.extend(list(csv_reader))
                file_name = CHECKER_PATH+"/"+files_in_checker_dir[i]
                df = pd.read_csv(file_name,delimiter=",",header=None)
                values.extend(list(df[2]))
                absolute_max_value = df[2].abs().max()
                if( absolute_max_value > abs(worst_value)):
                    max_row = df[2].abs().idxmax()
                    worst_value = df[2][max_row]
                    coordinate = os.path.basename(file_name).split("_")
                    if not (len(coordinate) > 2 and coordinate[0].lstrip("-").isdigit() and coordinate[1].lstrip("-").isdigit()):
                        coordinate = [0,0]
                    worst_x = (float(coordinate[0])/10) + (PARITION_SIZE/2) + df[0][max_row]
                    worst_y = (float(coordinate[1])/10) + (PARITION_SIZE/2) + df[1][max_row]

        if filecnt==0:
            LOGGER.error("ERROR: File containing "+ analysis_type+" entries not found.")
            return {"Avalibility":"None"}
        
        #for i in range(0,len(list(reader))-2):
        #    if len(list(reader)[i]) != 3:
        #        reader.remove(reader[i])
        #        LOGGER.error("ERROR: incorrect value "+ reader[i] + "is removed.")

        sortedlist = values
        sortedlist.sort(key=float)
        # sortedlist =sorted(values, key=float)
                
        size_of_array = len(sortedlist)
        statistical_stats=OrderedDict() 
        statistical_stats["min"] =checkValueExistence(sortedlist[0],"min")  
        pct10 = int(size_of_array / 10)  
        statistical_stats["10th"] = checkValueExistence(sortedlist[pct10],"10th")  
        pct25 = int(size_of_array / 4)  
        statistical_stats["25th"] = checkValueExistence(sortedlist[pct25],"25th")
        pct50 = int(size_of_array / 2)  
        statistical_stats["50th"] = checkValueExistence(sortedlist[ pct50],"50th")
        pct75 = int(size_of_array * 0.75)  
        statistical_stats["75th"] = checkValueExistence(sortedlist[ pct75],"75th")
        pct90 = int(size_of_array * 0.9)  
        statistical_stats["90th"] = checkValueExistence(sortedlist[ pct90],"90th")
        statistical_stats["max"] = checkValueExistence(sortedlist[size_of_array -1],"max")
        statistical_stats["marker_x"] = checkValueExistence(worst_x,"marker_x")
        statistical_stats["marker_y"] = checkValueExistence(worst_y,"marker_y")
        creatingTMDSscript(statical_analysis_dict[analysis_type][0], statical_analysis_dict[analysis_type][1],
                        analysis_type,worst_x,worst_y)

        return statistical_stats

    # Finds and returns runtime analysis stats in the form of a dictionary
    def getRuntimeStats():
        runtime_stats={}
        target_prep=""
        optim_stats={}
        optim_stats[0]=""
        optim_stats[1]=""
        optim_stats[2]=""
        optim_stats[3]=""
        CTM_exec_time=""
        QTM_exec_time=""
        Total_Fermi_Runtime=""
        postprocess_exec_time=""
        The_checker_runtime=""
        LOGGER.info("INFO: Finding Target_Prep_Runtime from targetprep_exec")
        if os.path.isfile(FERMI_PATH+"/targetprep_exec"):
            target_prep=open(FERMI_PATH+"/targetprep_exec").readlines()
            target_prep=target_prep[0].split(" ")[5].rstrip()
        else:
            LOGGER.error("ERROR:"+FERMI_PATH+"/targetprep_exec not found")
        
        LOGGER.info("INFO: Finding CTM_fg,QTM_fg,QTM exec time,CTM exec time,PostProcess_exec_time and Total_Fermi_Runtime from optim_exec")
        if os.path.isfile(FERMI_PATH+"/optim_exec"):
            cmd="grep f/g "+FERMI_PATH+"/optim_exec | cut -d ' ' -f3"
            file=os.popen(cmd)
            optim_stats=file.read().split("\n")
            cmd="grep 'CTM exec time' "+FERMI_PATH+"/optim_exec | cut -d ' ' -f5"
            file=os.popen(cmd)
            CTM_exec_time=file.read().rstrip("\n")
            cmd="grep 'QTM exec time' "+FERMI_PATH+"/optim_exec | cut -d ' ' -f5"
            file=os.popen(cmd)
            QTM_exec_time=file.read().rstrip("\n")
            cmd="grep 'PostProcess exec time' "+FERMI_PATH+"/optim_exec | cut -d ' ' -f5"
            file=os.popen(cmd)
            postprocess_exec_time=file.read().rstrip("\n")

            Total_Fermi_Runtime=round(float(CTM_exec_time) + float(QTM_exec_time) + float(postprocess_exec_time),2)
            #d=datetime(1,1,1) + sec
            #Total_Fermi_Runtime="%dd %d:%d:%d" % (d.day-1, d.hour, d.minute, d.second)
        else:
            LOGGER.error("ERROR:"+FERMI_PATH+"/optim_exec not found")

        LOGGER.info("INFO: The_checker_runtime from output/CheckerOnly.index.html")
        if os.path.isfile(CHECKER_PATH+"/output/CheckerOnly.index.html"):
            cmd="grep 'Duration' "+CHECKER_PATH+"/output/CheckerOnly.index.html | cut -d '>' -f5|cut -d '<' -f1"
            file=os.popen(cmd)
            The_checker_runtime=file.read().split("\n")[0].split(":")
            days=int(The_checker_runtime[0].split("d")[0])
            hours=int(The_checker_runtime[0].split("d")[1].replace(" ","0"))
            min=int(The_checker_runtime[1])
            sec=int(The_checker_runtime[2])
            The_checker_runtime=sec+60*min+60*60*hours+60*60*24*days
        else:
            LOGGER.error("ERROR:"+CHECKER_PATH+"/output/CheckerOnly.index.html not found")
        
        if optim_stats[1]!="" and optim_stats[2]!="" and optim_stats[3]!="":
            QTM_fg=float(optim_stats[1])+float(optim_stats[2])+float(optim_stats[3])
        else:
            QTM_fg=""

        runtime_stats["Target_Prep_Runtime"]=checkValueExistence(target_prep,"Target_Prep_Runtime")
        runtime_stats["CTM_fg"]=checkValueExistence(optim_stats[0],"CTM_fg")
        runtime_stats["QTM_fg"]=checkValueExistence(QTM_fg,"QTM_fg")
        runtime_stats["CTM_exec_time"]=checkValueExistence(CTM_exec_time,"CTM_exec_time")
        runtime_stats["QTM_exec_time"]=checkValueExistence(QTM_exec_time,"QTM_exec_time")
        runtime_stats["PostProcess_exec_time"]=checkValueExistence(postprocess_exec_time,"PostProcess_exec_time")
        runtime_stats["Total_Fermi_Runtime"]=checkValueExistence(Total_Fermi_Runtime,"Total_Fermi_Runtime")
        runtime_stats["The_checker_runtime"]=checkValueExistence(The_checker_runtime,"The_checker_runtime")
        
        return runtime_stats


    # Finds and returns stats for run,machine,fermi model, and test table in the form of a dictionary
    def getRunStats():
        host=""
        user=""
        time=""
        num_of_controller_files=0
        revision_date = ""
        revision = ""
        revision_branch = ""
        
        # Finding revision
        LOGGER.info("INFO: Finding revision branch and commit from logs/controller*.log")
        fermi_logs_dir = os.listdir(FERMI_PATH + "/logs")
        for file in fermi_logs_dir:
            if "controller" in file and "verbose" not in file:
                num_of_controller_files=num_of_controller_files+1


        if num_of_controller_files !=0:
            controller_log = [f_name for f_name in fermi_logs_dir if f_name.startswith('controller')][0]
            controller_log_fd = open(FERMI_PATH+"/logs/"+controller_log).readlines()
            is_info_str_found = False
            for line in controller_log_fd:
                if "Build information" in line:
                    is_info_str_found = True
                if is_info_str_found:
                    if not revision_date and "build" in line:
                        LOGGER.info("INFO: Finding revision date from controller log ")
                        revision_date = line.split("(")[-1].split(" ")[0]
                    if not revision and "revision" in line:
                        LOGGER.info("INFO: Finding revision and branch name from controller log ")
                        revision = line.split(" ")[-1].replace("'","")
                        revision_branch = revision.split("-0-")[0].split("/")[-1]
        else: 
            LOGGER.error("ERROR: controller*.log not found")
        
        
        # Finding time
        num_of_cdpcompletion_files=0
        LOGGER.info("INFO: Finding time from logs/cdpcompletion*.log")
        for file in os.listdir(FERMI_PATH + "/logs"): 
            if "cdpcompletion" in file:
                cmd= "grep ProgramStartEpoch "+ FERMI_PATH + "/logs/"+file+"  | cut -d '}' -f1 | cut -d '|' -f2"
                process = os.popen(cmd)
                time = process.read()
                sec=timedelta(seconds=float(time))-timedelta(hours=5)
                time=datetime(1970,1,1)+sec
                num_of_cdpcompletion_files=num_of_cdpcompletion_files+1
                break
        if num_of_cdpcompletion_files==0:    
            LOGGER.error("ERROR: cdpcompletion*.log not found")
            
        # Finding User and Host
        Design_size=""
        LOGGER.info("INFO: Finding User and Host from divi*.log")
        path=FERMI_PATH+"/logs/import"
        if os.path.isdir(path):
            for file in os.listdir(path):
                if ".log" in file:
                    cmd= "grep SGE_O_HOST "+path+ "/"+file+" | cut -d '=' -f2"
                    process = os.popen(cmd)
                    host = process.read()
                    host = host.replace("\"","")

                    cmd= "grep SGE_O_LOGNAME "+path+ "/"+file+" | cut -d '=' -f2"
                    process = os.popen(cmd)
                    user = process.read()
                    user = user.replace("\"","")
                    
                    cmd= "grep millimeters: "+path+ "/"+file
                    process = os.popen(cmd)
                    Design_size = process.read().split(" ")
                    Design_size = Design_size[len(Design_size)-3].rstrip("mm")+" x "+ Design_size[len(Design_size)-5].rstrip("mm")
                elif len(os.listdir(path))<2:
                    LOGGER.error("ERROR: divi*.log not found")
        else:
            LOGGER.error("ERROR: "+path+ " not found")

        # Finding testname, process_cond_arr, Design_size and tmod_name
        LOGGER.info("INFO: Finding testname,tmod_name,Design_size and process_condition from d2sflow.ini")
        TEST_NAME=""
        tmod_name=""
        process_cond_arr={} 
        process_condition=""
        for i in range(0,9):
            process_cond_arr[i]=""

        file_path=FERMI_PATH+"/input/d2sflow.ini"
        if os.path.isfile(file_path):
            fd_d2sflow=open(file_path).readlines()
            for line in fd_d2sflow:
                if "idcode" in line:
                    TEST_NAME=line.split("=")[1].rstrip()
                if "tmod" in line:
                    tmod_name=line.split("/")
                    length=len(tmod_name)
                    tmod_name=tmod_name[length-1]
                if "nominal_tag" in line:
                    process_cond_arr[0]=line.split("=")[1].rstrip()
                if "plus_focus_tag" in line:
                    process_cond_arr[1]=line.split("=")[1].rstrip()
                if "minus_focus_tag" in line:
                    process_cond_arr[2]=line.split("=")[1].rstrip()
                if "plus_dose_tag" in line:
                    process_cond_arr[3]=line.split("=")[1].rstrip()
                if "minus_dose_tag" in line:
                    process_cond_arr[4]=line.split("=")[1].rstrip()
                if "nominal_weight" in line:
                    process_cond_arr[5]=line.split("=")[1].rstrip()
                if "dose_weight" in line:
                    process_cond_arr[6]=line.split("=")[1].rstrip()
                if "focus_weight" in line:
                    process_cond_arr[7]=line.split("=")[1].rstrip()
                if "match_to_nominal_weight" in line:
                    process_cond_arr[8]=line.split("=")[1].rstrip()
            process_condition=process_cond_arr[0]+"_"+process_cond_arr[1]+"_"+process_cond_arr[2]+"_"+process_cond_arr[3]+"_"+process_cond_arr[4]+"_"+process_cond_arr[5]+"_"+process_cond_arr[6]+"_"+process_cond_arr[7]+"_"+process_cond_arr[8]
        else:
            LOGGER.error("ERROR: "+file_path+" not found")
        
        if process_condition == "________":
            process_condition=""
        # Get mask file size
        file_size=""
        LOGGER.info("INFO: Finding mask_file_size from input/custom_checks.args")
        if os.path.isfile(CHECKER_PATH+"/input/custom_checks.args"):
            cmd="grep input_mask "+CHECKER_PATH+"/input/custom_checks.args | cut -d ' ' -f2 "
            file=os.popen(cmd)
            file_path=file.read()
            file_path=file_path.rstrip().split("/")
            length=len(file_path)
            file_path=FERMI_PATH+"/"+file_path[length-2]+"/"+file_path[length-1]
            if os.path.isfile(file_path):
                file_size = float(os.stat(file_path).st_size)/(1024*1024)
                file_size=str(round(file_size,2))
            else:
                LOGGER.error("ERROR: "+file_path+" not found.")
        else:
            LOGGER.error("ERROR: "+CHECKER_PATH+"/input/custom_checks.args not found.")

        # Get name for test table
        LOGGER.info("INFO: Finding name for test table")
        os.listdir(FERMI_PATH + "/logs")
        #---------------------------------------------------------------------------------------------------
        cmd="ls "+FERMI_PATH+"/input/*.oas | xargs -n 1 basename "
        file=os.popen(cmd) 
        name=file.read().rstrip().rstrip(".oas")

        # Get GPU
        GPU=0
        LOGGER.info("INFO: Finding number of GPUs")
        if "optim_0" in os.listdir(FERMI_PATH):
            cmd ="ls "+FERMI_PATH+"/optim_[[:digit:]]*" 
            file=os.popen(cmd)
            optim_files=file.read().rstrip("\n").split("\n")
            GPU=int(math.ceil(len(optim_files)/2))
            # print(GPU)
        else:
            GPU=""

        #Get total errors and per partition value
        total_errors=""
        max_errors=""
        LOGGER.info("INFO: Finding total_errors and max_error")
        path=CHECKER_PATH+"/output/CheckerOnly.checker_part.html"
        if os.path.isfile(path):
            fd_checker_only_html=open(path).readlines()
            line=""
            for line_no in range(len(fd_checker_only_html)):
                if "total_errors" in fd_checker_only_html[line_no]:
                    line=fd_checker_only_html[line_no].split() #this split line with spaces
                    break
            for value in line:
                if "id=\"total_errors" in value:
                    total_errors = value.split(">")[1].split("<")[0] #get value using parsing 
                elif "id=\"max_errors_per_partition" in value:
                    max_errors = value.split(">")[1].split("<")[0] #get value using parsing

        else:
            LOGGER.error("ERROR: "+path+" not found")

        # get optimizer iterations, grid and partition 
        opt_iter=""
        grid=""
        partition=""
        ncol=""
        nrow=""
        LOGGER.info("INFO: Finding optimizer iterations, grid and partition from "+FERMI_PATH+"/logs/optimization/fermi*.log")
        if os.path.isdir(FERMI_PATH+"/logs/optimization"):#-----------------------------------------------------------------------listdir and fermi
            cmd="grep 'optimizer iterations' "+FERMI_PATH+"/logs/optimization/fermi*.log "
            file=os.popen(cmd)
            opt_iter=file.read()
            opt_iter=opt_iter.split("\n")[0].split(" ")
            opt_iter=opt_iter[len(opt_iter)-1]

            cmd="grep 'my nrows' "+FERMI_PATH+"/logs/optimization/fermi*.log "
            file=os.popen(cmd)
            nrow=file.read().split("\n")[0].split(" ")
            nrow=nrow[len(nrow)-1]
            cmd="grep 'my ncols' "+FERMI_PATH+"/logs/optimization/fermi*.log "
            file=os.popen(cmd)
            ncol=file.read().split("\n")[0].split(" ")
            ncol=ncol[len(ncol)-1]
            partition=nrow+" x "+ncol

            cmd="grep 'mask pixel size (nm)' "+FERMI_PATH+"/logs/optimization/fermi*.log "
            file=os.popen(cmd)
            grid=file.read().split("\n")[0].split(" ")
            grid=grid[len(grid)-1]        
        else:
            LOGGER.error("ERROR: "+FERMI_PATH+"/logs/optimization directory not found. ")

        # calculate runtime with 50 GPUs
        Runtime_with_50GPUs=""
        Runtime_with_Single_GPU =""
        if (grid!="" and ncol != "" and ncol!= "" ):
            area = 26000*33000/6.0
            design_size = 4.096*4.096*float(grid)*float(grid)*float(nrow)*float(ncol)
            Runtime_with_50GPUs =round(24*3600*design_size/area,2)
            # calculate runtime with single GPU
            Runtime_with_Single_GPU = round(50*24*3600*design_size/area,2)
        else:
            LOGGER.error("ERROR: Runtime_with_Single_GPU and Runtime_with_50GPUs can not be calculated")
        # Putting values in dictionary
        run_stats={}
        run_stats["Fermi_ID"]=os.path.basename(FERMI_PATH)
        run_stats["Checker_id"]=os.path.basename(CHECKER_PATH)
        run_stats["GPU"]= checkValueExistence(GPU,"GPU")
        run_stats["expect_run_time_50_GPU"]= checkValueExistence(Runtime_with_50GPUs,"expect_run_time_50_GPU")
        run_stats["expect_run_time_1_GPU"]= checkValueExistence(Runtime_with_Single_GPU,"expect_run_time_1_GPU")
        run_stats["User"]= checkValueExistence(user.rstrip("\n"),"User")
        run_stats["Name"]= checkValueExistence(name.rstrip("\n"),"Name")
        run_stats["Max_err_per_partion"]= checkValueExistence(max_errors.rstrip("\n"),"Max_err_per_partion")
        run_stats["Total_errors"]= checkValueExistence(total_errors.rstrip("\n"),"Total_errors")
        run_stats["Design_size"]= checkValueExistence(Design_size.rstrip("\n"),"Design_size")
        run_stats["Mask_file_size"]= checkValueExistence(file_size.rstrip("\n"),"Mask_file_size")
        run_stats["Machine_Name"]= checkValueExistence(host.rstrip("\n"),"Machine_Name")
        run_stats["Run_date_time"]= checkValueExistence(time,"Time")
        run_stats["revision_branch"]= checkValueExistence(revision_branch.rstrip("\n"),"revision_branch")
        run_stats["revision_commit"]= checkValueExistence(revision.rstrip("\n"),"revision_commit")
        run_stats["revision_date"]= checkValueExistence(revision_date.rstrip("\n"),"revision_date")
        run_stats["Fermi_job_name"]= checkValueExistence(TEST_NAME.rstrip("\n"),"Fermi_job_name")
        run_stats["tmod_name"]= checkValueExistence(tmod_name.rstrip("\n"),"tmod_name")
        run_stats["process_condition"]= checkValueExistence(process_condition,"process_condition")
        run_stats["partition"]= checkValueExistence(partition.rstrip("\n"),"partition")
        run_stats["grid"]= checkValueExistence(grid.rstrip("\n"),"grid")
        run_stats["optimizer_iterations"]= checkValueExistence(opt_iter.rstrip("\n"),"optimizer_iterations")
        return run_stats

    # Finds and returns geometric analysis stats in the form of a dictionary.
    def getGeometricStats():
        path_html=CHECKER_PATH+"/output/CheckerOnly.checker_part.html"
        path_csv=CHECKER_PATH+"/output/CheckerOnly.checker_part.csv"
        geo_stats={}
        if os.path.isfile(path_html) and os.path.isfile(path_csv):
            fd_checker_only_html=open(path_html).readlines()
            fd_checker_only_csv=open(path_csv).readlines()
            if len(fd_checker_only_html) == 0:
                LOGGER.error("ERROR: File "+path_html+" is empty")

            for line_no in range(len(fd_checker_only_html)):
                if ">MRC Area" in fd_checker_only_html[line_no]:
                    error_name="MRC Area"
                    error_type="9:0"
                elif ">MRC Spacing" in fd_checker_only_html[line_no]:
                    error_name="MRC_Spacing"
                    error_type="9:2"
                elif ">MRC Width" in fd_checker_only_html[line_no]:
                    error_name="MRC Width"
                    error_type="9:1"
                else:
                    continue
                
                
                count=int(fd_checker_only_html[line_no].replace("</td></tr>\n","").split(">")[-1])
                LOGGER.info("INFO:ErrorName:"+error_name+" ErrorType:"+error_type+" with error count:"+str(count)+" found at line no:"+str(line_no+1)+" in CheckerOnly.checker_part.html")

                # MAXIMUM VALUE
                max_val=0
                marker_x = 0
                marker_y = 0

                if count>0:
                    if fd_checker_only_csv:
                        for line_no in range(len(fd_checker_only_csv)):
                            if error_type+"," in fd_checker_only_csv[line_no]:
                                max_val=fd_checker_only_csv[line_no].split(",")[1]
                                LOGGER.info("INFO: ErrorType:"+error_type+" with Max Value:"+max_val+" found at line no:"+str(line_no+1)+" in CheckerOnly.checker_part.csv" )
                                break
                        if not max_val:
                            LOGGER.error("ERROR: ErrorType:"+error_type+" couldnot found Max Value in CheckerOnly.checker_part.csv" )
                    else:
                        LOGGER.error("ERROR: ErrorType:"+error_type+" couldnot found Max Value because CheckerOnly.checker_part.csv not exists" )
                        
                    for l_no in range(len(fd_checker_only_html)):
                        if "name=\""+error_type in fd_checker_only_html[l_no]:
                            value=fd_checker_only_html[l_no+4]
                            value=value.split("</a>")[0].split()
                            marker_x = value[-3]
                            marker_y = value[-1]
                            LOGGER.info("Locations of ErrorType: "+error_type+" found at line no:"+str(l_no+1)+" in CheckerOnly.checker_part.html\n")
                    
                    creatingTMDSscript("mrc",error_type,error_name,float(marker_x),float(marker_y))
                
                error_name=error_name.replace(" ","_")
                geo_stats[error_name+"_count"]=count
                geo_stats[error_name+"_min_max_value"]= round(float(max_val),2)
                geo_stats[error_name+"_marker_x"] = marker_x
                geo_stats[error_name+"_marker_y"] = marker_y
        else:
            LOGGER.error("ERROR:Existance of "+path_html+": "+os.path.isfile(path_html)+"and Existance of "+path_csv+": "+os.path.isfile(path_csv))

        return geo_stats


    # def parser_main(_path,_list_ids):
    global CHECKER_PATH, FERMI_PATH, LOGGER

    #Configure collective parser log that contain one liner for all entered ids 
    parser_main_logger = logging.getLogger("collective_parser_logger")
    parser_main_logger.setLevel(logging.DEBUG)
    debug_log = logging.FileHandler(os.path.join(os.getcwd(), 'parser.log'), mode='w')
    debug_log.setLevel(logging.INFO)
    parser_main_logger.addHandler(debug_log)


    for id_num in _list_ids:
        CHECKER_PATH=_path+"/"+str(id_num)
        checker_id=str(id_num)
        if not os.path.isdir(CHECKER_PATH):
            parser_main_logger.info(str(id_num)+":: ERROR:Directory with JOB_ID:"+str(id_num)+" doesnot exist in "+_path)
            continue
        elif not os.path.isfile(CHECKER_PATH+"/input/d2sflow.ini"):
            parser_main_logger.info(str(id_num)+":: ERROR:"+CHECKER_PATH+"/input/d2sflow.ini" " not found.")
            continue
        elif (checkFlow() != "CheckerOnly"):
            parser_main_logger.info(str(id_num)+":: ERROR:"+CHECKER_PATH +" is not Checker flow.")
            continue
        else:
            fermi_id=getFermiId() 
            if fermi_id==-1:
                parser_main_logger.info(str(id_num)+":: ERROR:"+CHECKER_PATH+"/input/custom_checks.args not found.")
                continue
        
        # qor directory creation in checker directory
        if os.path.isdir(CHECKER_PATH+"/qor"):
            if os.path.isdir(CHECKER_PATH+"/qor_backup"):
                os.system("rm -r "+CHECKER_PATH+"/qor_backup")
            os.system("mv "+CHECKER_PATH+"/qor "+CHECKER_PATH+"/qor_backup")


        os.system("mkdir -p "+CHECKER_PATH+"/qor/logs/parsing_log")
        os.system("mkdir "+CHECKER_PATH+"/qor/logs/tmds_log")
        os.system("mkdir "+CHECKER_PATH+"/qor/script")
        os.system("mkdir "+CHECKER_PATH+"/qor/asset")

        # Configuring logging
        LOGGER=logging.getLogger("individual_logger")
        LOGGER.setLevel(logging.DEBUG)
        # to log debug messages                               
        debug_log = logging.FileHandler(CHECKER_PATH+"/qor/logs/parsing_log/info.log")
        
        debug_log.setLevel(logging.INFO)
        # to log errors messages
        error_log = logging.FileHandler(CHECKER_PATH+"/qor/logs/parsing_log/error.log")
        error_log.setLevel(logging.ERROR)

        LOGGER.addHandler(debug_log)
        LOGGER.addHandler(error_log)

        LOGGER.info("INFO: "+CHECKER_PATH + " found")
        FERMI_PATH=_path+"/"+fermi_id 
        
        # Dump data to ini file
        LOGGER.info("INFO: Dumping data into Fermi_stats.txt")
        config = configparser.ConfigParser()
        config["Main_Stats"]=getRunStats()
        config["Runtime_Analysis_Stats"] = getRuntimeStats()
        config["Geometric_Analysis_Stats"] = getGeometricStats()
        for statistical_key in statical_analysis_dict:
            print(statical_analysis_dict[statistical_key][0])
            config["Statistical_Analysis:"+ statistical_key]=getStatisticalAnalysisStats(statistical_key)
        with open(CHECKER_PATH+'/qor/Fermi_stats.txt', 'w') as configfile:
            config.write(configfile)  
        # Append exit in tcl scripts   
        for file in os.listdir(CHECKER_PATH + "/qor/script"):
            fd = open(CHECKER_PATH + "/qor/script/"+file,"a")
            fd.write("exit \n")
            fd.close()

        # Copying graph files 
        cmd = "cp "+CHECKER_PATH+"/output/*.png "+CHECKER_PATH+"/qor/asset"
        os.system(cmd)

        #Taking screenshots using created scripts
        #tcl_script_path=CHECKER_PATH+"/qor/script/epe_clips.tcl"
        # if os.path.isfile(tcl_script_path):
        #     cmd="tmds -l "+CHECKER_PATH+"/"+DIR_NAME+"/qor/logs/tmds_log/epe_clips.log -E \"source "+tcl_script_path+"\""
        #     os.system(cmd)

        # tcl_script_path=CHECKER_PATH+"/qor/script/mrc_clips.tcl"
        # if os.path.isfile(tcl_script_path):
        #     cmd="tmds -l "+CHECKER_PATH+"/"+DIR_NAME+"/qor/logs/tmds_log/mrc_clips.log -E \"source "+tcl_script_path+"\""
        #     os.system(cmd)


        parser_main_logger = logging.getLogger("collective_parser_logger")
        parser_main_logger.info(str(id_num)+":: Successfully parsed")

        # for log_name in ["collective_parser_logger","individual_logger"]:
        #     log = logging.getLogger(log_name)
        #     for i in list(log.handlers):
        #         log.removeHandler(i)
        #         i.flush()
        #         i.close()


if __name__ == "__main__":
    # Reading Arguments
    help_str = "This script provides two actions, parsing for given number of job ids or \
        recording data to database for given number of job-ids. --path and --job_id argument\
        assign to both groups. "
    # my_parser = argparse.ArgumentParser()
    my_parser = argparse.ArgumentParser(description=help_str)
    my_parser.add_argument("-l","--location", action="store", type=str, required=True, help="Location of design folder")
    my_parser.add_argument("-id","--job_id", action="store", type=str, help="Checker Job ID range e.g 5:11 or single value e.g 10 or comma separated values e.g 10,15,11...")
    parse_group = my_parser.add_argument_group("parse_group", "Arguments available for parsing")
    parse_group.add_argument("-p","--parse",action="store_true", help="This enables parsing option")
    record_group = my_parser.add_argument_group("record_group", "Arguments available for recording to database")
    record_group.add_argument("-r","--record",action="store_true", help="This enables recording option")
    record_group.add_argument("-f","--force",action="store_true", help="This enables force flag for current job")
    record_group.add_argument("-c","--cronjob",action="store_true", help="This enables cron option for provided path")


    # Checking any of action specified or not
    args = my_parser.parse_args()
    if not (args.parse or args.record):
        my_parser.error("No action requested, add --parse or --record")
        exit

    # Checking input location is valid or not
    if not (os.path.isdir(args.location)):
        my_parser.error("Input location is not a valid directory.")
        exit()
    location = os.path.normpath(args.location)

    if args.cronjob:
        list_ids = os.listdir(location)
        sorting_list=[location +"/"+ file for file in list_ids]
        sorting_list.sort(key=os.path.getctime)
        list_ids = [os.path.basename(file) for file in list_ids]
    else:
        # Argument Parsing  
        if(args.job_id.find(":") == -1 and args.job_id.find(",") == -1 ):
            if not (args.job_id.isdigit()):
                my_parser.error("Input job-id is/are not valid")
                exit()
            JOB_ID=args.job_id
            starting_job_id=int(JOB_ID)
            ending_job_id=int(JOB_ID)
            list_ids=range(starting_job_id,ending_job_id+1)
        elif(args.job_id.find(":") != -1):
            JOB_ID=args.job_id.split(":")
            starting_job_id=int(JOB_ID[0])
            ending_job_id=int(JOB_ID[1])
            list_ids=range(starting_job_id,ending_job_id+1)
        elif (args.job_id.find(",") != -1):
            list_ids=args.job_id.split(",")

    # try: 
    if args.parse:
        #Parsing data
        parsingData(location, list_ids)

    if args.record:
        enteringDataIntoDatabase(location, list_ids, args.force, args.cronjob)
    # except Exception as e:
        # print(e)


    