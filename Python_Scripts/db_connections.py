import yaml
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from pymongo import MongoClient
import importlib.resources as resources
from sqlalchemy import create_engine


db_connections = {
    'sqlite': {},
    'postgresql': {},
    'mongodb': {}
}

class DbConnections:

    @staticmethod
    def get_package_file_path(
        pacakge_path: str,
        file_name: str
    ) -> Path:
        """
        get the absolute path to the file in the package
        """
        path = (
            resources
            .files(pacakge_path)
            .joinpath(file_name)
        )
        return path

    # @staticmethod
    # def get_config(
    #     config_name: str,
    #     db_name: str
    # ):
    #     """
    #     the expected config file must be in the _configs folder
    #     """
    #     assert config_name is not None, "config_name must be provided"
    #     assert db_name is not None, "db_name must be provided"
    #
    #     with (
    #         resources
    #         .files("wm_utils._configs")
    #         .joinpath(config_name)
    #         .open("r") as f
    #     ):
    #         config = yaml.safe_load(f)
    #
    #     db_config = config.get(db_name)
    #     if db_config is None:
    #         raise ValueError("db_config not found in config")
    #
    #     return db_config
    @staticmethod
    def get_config(config_name: str, db_name: str):

        assert config_name is not None, "config_name must be provided"
        assert db_name is not None, "db_name must be provided"

        with open(config_name, "r") as f:
            config = yaml.safe_load(f)

        db_config = config.get(db_name)

        if db_config is None:
            raise ValueError("db_config not found in config")

        return db_config

    @staticmethod
    def get_postgresql_connection(
        config_name: str = 'db_config.yaml',
        db_name: str = 'wm_price_db'
    ):  
        # check if the connection is already established
        if db_name in db_connections['postgresql']:
            return db_connections['postgresql'][db_name]
        
        # get the config
        db_config = DbConnections.get_config(
            db_name=db_name,
            config_name=config_name
        )
        
        # create the engine
        db_connections['postgresql'][db_name] = \
            create_engine(f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['dbname']}")
        
        return db_connections['postgresql'][db_name]

    
    @staticmethod
    def get_mongodb_connection(
        config_name: str = 'central_config_all.yaml',
        db_name: str = 'wm_prod'
    ):
        # check if the connection is already established
        if db_name in db_connections['mongodb']:
            return db_connections['mongodb'][db_name]
        
        # get the config
        db_config = DbConnections.get_config(
            db_name=db_name,
            config_name=config_name
        )

        # get pem file path
        pem_file_path = DbConnections.get_package_file_path(
            pacakge_path="wm_utils._configs",
            file_name="global-bundle.pem"
        )
        pem_file_path = str(pem_file_path)
        
        # create the connection
        db_connections['mongodb'][db_name] = MongoClient(
            host=db_config['host'], 
            port=db_config['port'],
            username=db_config['user'],
            password=db_config['password'],
            tls=db_config['tls'],
            tlsCAFile=pem_file_path,
            replicaSet=db_config['replicaSet'],
            readPreference=db_config['readPreference'],
            retryWrites=db_config['retryWrites']
        )
        
        return db_connections['mongodb'][db_name]

if __name__ == "__main__":
    mongo_conn = DbConnections.get_mongodb_connection()
    print(mongo_conn)

    db = mongo_conn.wm_research

    collections = db.list_collection_names()
    print(collections)
