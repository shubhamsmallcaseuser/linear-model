# -*- coding: utf-8 -*-
"""
Created on Tue Oct 18 17:05:56 2022

@author: manur
"""








import os
from Python_Scripts.ST import *
from Python_Scripts import tsa, arma
#%%
import Python_Scripts.QuantBacktester as qd
#%%
import Python_Scripts.mass as mk
#%%
from scipy import stats, signal
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
#%%


wSize = [45,60,90,100]

#%%
excelReaderfObj = qd.ExcelInputReader()
universeFilePath = r'D:\Linear Model\data\Universe\TradingDays.xlsx' #'G:/.shortcut-targets-by-id/0B7f_UMMZHM_JNXljMVVXY2VPcHM/Investment Research_N/Manu/Universe/TradingDays.xlsx'
allTradingDatesDf = excelReaderfObj.getTradingDatesDataFrame(excelFile= universeFilePath, sheetName = 'Sheet1')
allTradingDatesDf.reset_index(drop = True, inplace = True)
ricDict = {'.NSEI': r'D:\Linear Model\data\Universe\INDTradingDays.xlsx'} #'G:/.shortcut-targets-by-id/0B7f_UMMZHM_JNXljMVVXY2VPcHM/Investment Research_N/Manu/Universe/INDTradingDays.xlsx'}
priceDf = qd.UtilsQB().setDatFrame(allTradingDatesDf, ricDict)
#%%
#mainFolderPath = r'D:\Linear Model\data\RSI\Final'
mainFolderPath = os.path.join("data", "RSI", "Final", "NSEI")
freq = 'W'
existingFilePath = os.path.join(mainFolderPath, f"{freq}_allRebal.xlsx")
currentDf = excelReaderfObj.getDataFrame(existingFilePath, rowsToSkip = 0, columnsToSkip = 0)
currentDf.set_index('Date', inplace = True)
#%%
niftyCloseDf = priceDf[3][['.NSEI']]
#%%
def getDp(niftyCloseDf, dte,w):
    sim = mk.Match(niftyCloseDf.loc[niftyCloseDf.first_valid_index():], dte, windowSize=w, threshold=0.9)
    dp = sim.getDates()
    return dp  
#%%
def getSimulateDf(niftyCloseDf,dte,w, dp,  rep = 35):
    qRoi = niftyCloseDf.iloc[niftyCloseDf.index.get_loc(dp)-13:][:w+14]
    frCoff = tsa.FractionEstimate(np.log(qRoi), numLag=14, interval=0.1, confidence=0.95, tolerance=1e-4).getBest()
    if frCoff != 1:
        qFD = tsa.FractionalDifferencing(numLag=14, fraction= frCoff, tolerance=1e-4)
        qFR = qFD.getDifferencedSeries(np.log(qRoi))
        
        # print(qFR)
        qFRIC = arma.ModelSelection(qFR.values.flatten(),5,5).getICseries()
        qFRIC.sort_values("AIC", inplace= True)
        # print(qFRIC)
        p, q= qFRIC.loc[qFRIC.index[0]]['p'], qFRIC.loc[qFRIC.index[0]]['q']
        
        # print(p,q)
        mod = arma.Model(qFR, p = int(p), q = int(q))
        mod.getParams()
        
        oRoi =  niftyCloseDf.loc[:dte][-15:]
        oFD = tsa.FractionalDifferencing(numLag=14, fraction= frCoff, tolerance=1e-4)
        oFR = oFD.getDifferencedSeries(np.log(oRoi))
        
        sims = arma.SimulateFD(mod, init_Val=oFR.iloc[0].values.flatten(), repetition=rep).getFDValues()
        simPrice= []
        for i in range(rep):
            simPrice.append(tsa.BackOperation(niftyCloseDf.loc[:dte][-14:].values.flatten(), sims.iloc[:, i], fraction= frCoff).getPrediction().values.flatten())
        simulatedPriceDf = pd.DataFrame(simPrice).T
        ci = niftyCloseDf.index.get_loc(dte)
        simulatedPriceDf.index = niftyCloseDf.iloc[ci-13:ci+23].index
        
        return p, q, qRoi, qFR,qFRIC, oRoi, oFR, simulatedPriceDf
    else:
        return -999
    
#%%
def getBeta(niftyCloseDf,dte,w, dp,  rep = 35):
    qRoi = niftyCloseDf.iloc[niftyCloseDf.index.get_loc(dp)-13:][:w+14]
    frCoff = tsa.FractionEstimate(np.log(qRoi), numLag=14, interval=0.1, confidence=0.95, tolerance=1e-4).getBest()
    if frCoff != 1:
        qFD = tsa.FractionalDifferencing(numLag=14, fraction= frCoff, tolerance=1e-4)
        qFR = qFD.getDifferencedSeries(np.log(qRoi))
        
        # print(qFR)
        # qFRIC = arma.ModelSelection(qFR.values.flatten(),5,5).getICseries()
        # qFRIC.sort_values("AIC", inplace= True)
        # # print(qFRIC)
        # p, q= qFRIC.loc[qFRIC.index[0]]['p'], qFRIC.loc[qFRIC.index[0]]['q']
        
        # print(p,q)
        mod = arma.Model(qFR, p = int(8), q = int(0))
        params = mod.getParams()
        
        return params.loc['ar.L1']['Coefficient']
    else:
        return -999    
    
#%%
def remove_outliers_iqr(series):
    Q1 = series.quantile(0.25)
    Q3 = series.quantile(0.75)
    IQR = Q3 - Q1
    
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    
    return series[(series >= lower_bound) & (series <= upper_bound)]
#%%
def getComp(niftyCloseDf, predictionDf):
    mCol = niftyCloseDf.columns[0]
    tmpDf = niftyCloseDf.loc[predictionDf.index][[mCol]]
    tmpDf.loc[predictionDf.index,'Prediction'] = predictionDf.values
    
        
    
    mean_mCol = tmpDf[mCol].pct_change(1).mean()
    std_mCol = tmpDf[mCol].pct_change(1).std()
    
    mean_Prediction = tmpDf['Prediction'].pct_change(1).mean()
    std_Prediction = tmpDf['Prediction'].pct_change(1).std()
    
    # Correlation
    correlation = tmpDf[mCol].corr(tmpDf['Prediction'])
    
    ret_mCol = tmpDf.loc[tmpDf.index[-1]][mCol] /tmpDf.loc[tmpDf.index[0]][mCol] -1
    ret_Prediction = tmpDf.loc[tmpDf.index[-1]]['Prediction'] /tmpDf.loc[tmpDf.index[0]]['Prediction'] - 1
    
    return mean_mCol, mean_Prediction, ret_mCol, ret_Prediction, std_mCol, std_Prediction, correlation,tmpDf
    
 
#%%
def getCompBeta(niftyCloseDf, dte):
    mCol = niftyCloseDf.columns[0]
    tmpDf = niftyCloseDf[[mCol]]
    currentRet = tmpDf.loc[dte][mCol] / tmpDf.iloc[tmpDf.index.get_loc(dte) - 13][mCol] - 1
    fwdRet = tmpDf.iloc[tmpDf.index.get_loc(dte) + 13][mCol] /tmpDf.loc[dte][mCol] - 1

    return currentRet,fwdRet
#%%
testingPeriod = currentDf.loc['2014-01-03':'2024-06-07'].index
#%%
resultDf2 = pd.DataFrame(index = testingPeriod, columns = ['Mean_Act', 'Mean_Pred',
                                                          'Ret_Act' , 'Ret_Pred',
                                                          'Std_Act' , 'Std_Pred',
                                                          'Corr'])
#%%
resultDf2 = pd.DataFrame(index = testingPeriod, columns = ['Beta', 'Beta_Max', 'PastRet', 'FwdRet'])
#%%
for dte in testingPeriod:
    dpDf = getDp(niftyCloseDf,dte,45)
    if dpDf.shape[0] > 0:
        simPrices = []
        for dp in dpDf.index[0:1]:
            res = getSimulateDf(niftyCloseDf,dte,45, dp, 100)
            if res != -999:
                meanPred = res[7].apply(lambda row: remove_outliers_iqr(row).mean(), axis=1)
                # meanPred = res[7].mean(1)
                predictionDf = meanPred.iloc[meanPred.index.get_loc(dte):]
                res2 = getComp(niftyCloseDf, predictionDf)
                for i in range(0, len(resultDf2.columns)) : resultDf2.loc[dte][resultDf2.columns[i]] = res2[i]
    print(dte)

#%%
import numpy as np
#%%

for dte in testingPeriod:
    dpDf = getDp(niftyCloseDf,dte,90)
    if dpDf.shape[0] > 0:
        resAvg = []
        for dp in dpDf.index[0:5]:
            res = getBeta(niftyCloseDf,dte,90, dp, 100)
            if res != -999:
                resAvg.append(res)              
        res2 = getCompBeta(niftyCloseDf,dte)
        resultDf2.loc[dte]['Beta']  = np.mean(resAvg)
        resultDf2.loc[dte]['Beta_Max']  = np.max(resAvg)
        resultDf2.loc[dte]['PastRet']  = res2[0]
        resultDf2.loc[dte]['FwdRet']  = res2[1]
    print(dte)

#%%


#%%


resultDf2_clean = resultDf2.dropna()

#%%
resultDf2_clean['Diff'] = resultDf2_clean['FwdRet'] - resultDf2_clean['PastRet']

#%%
from scipy.stats import percentileofscore
#%%
def average_every_5_percentile(df):
    # percentile_averages = pd.DataFrame(index = range(5,105,5), columns = df.columns)

    for column in df.columns:
        # Drop NaN values
        col_clean = df[column].dropna()
        
        # Calculate averages for each 5-percentile range
        # ranges = {}
        # for i in range(0, 100, 5):
            # lower_value = np.percentile(col_clean, i)
            # upper_value = np.percentile(col_clean, i + 5)
            
            # Filter the column values within the current percentile range
            # within_percentiles = col_clean[(col_clean >= lower_value) & (col_clean < upper_value)]
            
            # Calculate the mean within this range
            # ranges[f'{i}-{i + 5}%'] = within_percentiles.mean()
            # percentile_averages.loc[i+5][column]  = within_percentiles.mean()
            # percentile_averages.loc[i+5][column + 'Max']  = within_percentiles.max()
            # percentile_averages.loc[i+5][column + 'Min']  = within_percentiles.min()
            
        percentile_column = df[column].apply(lambda x: percentileofscore(col_clean, x) if not pd.isnull(x) else np.nan)
    
            # Add the percentile column to the DataFrame
        df[f'{column}_percentile'] = percentile_column
        
        bins = list(range(0, 101, 5))  # [0, 5, 10, ..., 95, 100]
        labels = [f'{i}-{i+5}%' for i in range(0, 100, 5)]
        df[f'{column}_percentile_bin'] = pd.cut(df[f'{column}_percentile'], bins=bins, include_lowest=True)

        
        # percentile_averages[column] = ranges
    
    return df
#%%resultDf_clean
percentile_averages = average_every_5_percentile(resultDf2_clean)
#%%
X = percentile_averages.groupby('Ret_Act_percentile_bin')['Ret_Pred'].mean()
y = percentile_averages.groupby('Ret_Act_percentile_bin')['Ret_Act'].mean()
#%%
X = percentile_averages.groupby('Diff_percentile_bin')['Beta'].mean()
y = percentile_averages.groupby('Diff_percentile_bin')['Diff'].mean()
#%%
X = percentile_averages['Beta_Max']
y = percentile_averages['Diff']

#%%
model = LinearRegression()
model.fit(X.values.reshape(-1, 1), y.values)

# Predict y values using the model
y_pred = model.predict(X.values.reshape(-1, 1))

# Plot the data points
plt.scatter(X, y, color='blue', label='Data points')

# Plot the best fit line
plt.plot(X, y_pred, color='red', label='Best fit line')

# Adding labels and title
plt.xlabel('Pred')
plt.ylabel('Actual')
plt.title('Best Fit Line')
plt.legend()

# Show the plot
plt.show()




#%%
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
# Separate the columns into variables
X = percentile_averages['Mean_Pred'].values.reshape(-1, 1)  # Independent variable
y = percentile_averages['Mean_Act'].values  # Dependent variable
#%%
# Perform linear regression
model = LinearRegression()
model.fit(X, y)

# Predict y values using the model
y_pred = model.predict(X)

# Plot the data points
plt.scatter(percentile_averages['Mean_Pred'], percentile_averages['Mean_Act'], color='blue', label='Data points')

# Plot the best fit line
plt.plot(percentile_averages['Mean_Pred'], y_pred, color='red', label='Best fit line')

# Adding labels and title
plt.xlabel('Pred')
plt.ylabel('Actual')
plt.title('Best Fit Line')
plt.legend()

# Show the plot
plt.show()










# ----- From here ----------




#%%
sim = mk.Match(priceDf[3][['.NSEI']].loc[priceDf[3]['.NSEI'].first_valid_index():], '2020-06-08', windowSize=wSize[0], threshold=0.9)

#%%
ans = sim.getMatchIndex()
#%%
reg = sim.getRegime()

#%%
dp = sim.getDates()



#%%


#%%
import Python_Scripts.tsa as tsa
#%%

qRoi = niftyCloseDf.iloc[niftyCloseDf.index.get_loc(dp)-13: ][:90+14]
#%%

frCoff = tsa.FractionEstimate(qRoi, numLag=14, interval=0.1, confidence=0.95, tolerance=1e-4).getBest()
print(frCoff)

#%%

qFD = tsa.FractionalDifferencing(numLag=14, fraction= frCoff, tolerance=1e-4)
qFR = qFD.getDifferencedSeries(qRoi)

#%%
import Python_Scripts.arma as arma
#%%
qFR12IC = arma.ModelSelection(qFR.values.flatten(), 14, 14).getICseries()
qFR12IC.sort_values("AIC").head()
#%%
mod12 = arma.Model(qFR, p = 1, q = 0)
params = mod12.getParams()
#%%
rep = 35

oRoi =  priceDf[3][['.NSEI']].loc[:'2020-06-08'][-15:]
oFD = tsa.FractionalDifferencing(numLag=14, fraction= frCoff, tolerance=1e-4)
oFR = oFD.getDifferencedSeries(np.log(oRoi))

#%%
sims12 = arma.SimulateFD(mod12, init_Val=oFR.iloc[0].values.flatten(), repetition=rep).getFDValues()
#%%
fig, ax = plt.subplots(figsize=(24, 6))
simPrice= []
for i in range(rep):
    simPrice.append(tsa.BackOperation(priceDf[3][['.NSEI']].loc[:'2020-06-08'][-14:].values.flatten(), sims12.iloc[:, i], fraction= frCoff).getPrediction().values.flatten())
pd.DataFrame(simPrice).T.plot(ax=ax, color='r')
ax.get_legend().remove()




#%%

# ---------------------- Ends here ---------------- 



#%%
# Basic Libraries
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import random 
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
from scipy import stats
from copy import deepcopy
import datetime
plt.style.use('seaborn')
# 
# warnings
# import warnings 
# warnings.filterwarnings('ignore')


#%%
import gmm
import tsa
import arma
import garch
import regime
import hurst
import mass as mk

#%%
import Python_Scripts.QuantBacktester as qd
import pandas as pd
import numpy as np
from scipy.stats import norm
from scipy import stats

#%%

excelReaderfObj = qd.ExcelInputReader()

#%%
closeDf = excelReaderfObj.getDataFrame('../Investment Research_N/Manu/Universe/SC100TradingDays.xlsx', sheetName = 'Close')
closeDf.set_index('Date', inplace=True)
#%%

#%%
universeFilePath = '../Investment Research_N/Manu/Universe/TradingDays.xlsx'
allTradingDatesDf = excelReaderfObj.getTradingDatesDataFrame(excelFile= universeFilePath, sheetName = 'Sheet1', startDate = closeDf.first_valid_index())
allTradingDatesDf.reset_index(drop = True, inplace = True)
monthEndDatesDf = allTradingDatesDf.loc[allTradingDatesDf.groupby('YearMonth').Date.idxmax()]
monthEndDatesDf.sort_values(by=['Date'], inplace = True)

#%%

mergeObj = qd.Merger()
closeMergedDf = mergeObj.getMergedBymethodDf(allTradingDatesDf, closeDf)

#%%
rebalDates = ['2021-10-29',
'2021-11-30',
'2021-12-31',
'2022-01-31',
'2022-02-28',
'2022-03-31',
'2022-04-29',
'2022-05-31',
'2022-06-30',
'2022-07-29',
'2022-08-30',
'2022-09-30',
]
#%%
rebalDates = ['2012-09-12']


#%%
resultDf = pd.DataFrame(columns = ['Ret_Avg', 'Std_Avg', 'Avg_Ret', 'Avg_Std'], index = rebalDates)
resultDf14 = pd.DataFrame(columns = ['Ret_Avg', 'Std_Avg', 'Avg_Ret', 'Avg_Std'], index = rebalDates)

#%%

i  = 0

rebalDate = rebalDates[i]

#%%

wSize = [45,60,90,100]

sim = mk.Match(closeMergedDf, rebalDate, windowSize=wSize[0], threshold=0.85)
reg = sim.getRegime()

#%%

print(reg)
print(rebalDate)

#%%

indexLists = [1,2]
#%%
# reg= mk.SignalAnalysis(closeMergedDf, rebalDate, [1, 4, 7], windowSize=45, threshold=0.90).getCombined()
#%%
# sd= reg.iloc[[1,2,4,7]]['start'].values
# ed= reg.iloc[[1,2,4,7]]['end'].values

#%% ----- PLottting ------------
plt.figure(figsize=(24,6))
ax = plt.gca()
# sim.plotMatch(ax)
for i in indexLists:
    ax.plot(stats.zscore(closeMergedDf.loc[reg.iloc[i].start: reg.iloc[i].end].values), 
            label='{} to {}'.format(str(reg.iloc[i].start), str(reg.iloc[i].end)))
    
    print(i)
# ax.plot(stats.zscore(closeMergedDf.loc[reg.iloc[0].start: reg.iloc[0].end].values), color='k', lw=4, label='Query')
ax.legend()

plt.savefig('../Investment Research_N/smallcases/Model smallcase/Cash/LM/' +rebalDate +'_MF_SC100Df.png')

#%%

qReg = tsa.Preprocess(closeMergedDf, start=reg.start.iloc[indexLists[1]], end=reg.end.iloc[indexLists[1]]).getProcessedData()
qRegRet = tsa.Returns(qReg).getLogReturns()


#%%

qRoi = tsa.Preprocess(closeMergedDf, start=reg.end.iloc[indexLists[1]] - datetime.timedelta(21),).getProcessedData()[:90+14]
print(qRoi)

#%% ----- eExcel output ----------

# qRoi.to_excel('../Investment Research_N/smallcases/Model smallcase/Cash/LM/Qroi.xlsx')

#%%

frCoff = tsa.FractionEstimate(np.log(qRoi), numLag=14, interval=0.1, confidence=0.95, tolerance=1e-4).getBest()
print(frCoff)

#%%

qFD = tsa.FractionalDifferencing(numLag=14, fraction= frCoff, tolerance=1e-4)
qFR = qFD.getDifferencedSeries(np.log(qRoi))
qFR.plot()

#%%

qFR12 = qFR[:45]
qFR14 = qFR[:90]

#%%


oRoi = closeMergedDf.loc[:rebalDate][-15:]
oFD = tsa.FractionalDifferencing(numLag=14, fraction= frCoff, tolerance=1e-4)
oFR = oFD.getDifferencedSeries(np.log(oRoi))


#%%

rep = 35

#%%

# ---- 2 month ---------------

qFR12IC = arma.ModelSelection(qFR12.values.flatten(), 5, 5).getICseries()

qFR12IC.sort_values("BIC").head()


#%%

mod12 = arma.Model(qFR12, p = 0, q = 1)
# mod12 = arma.Model(qFR12, p = 1, q = 0)
mod12.getParams()



#%%

sims12 = arma.SimulateFD(mod12, init_Val=oFR.iloc[0].values.flatten(), repetition=rep).getFDValues()

#%%

fig, ax = plt.subplots(figsize=(24, 6))
simPrice= []
for i in range(rep):
    simPrice.append(tsa.BackOperation(oRoi.values.flatten(), sims12.iloc[:, i], fraction= frCoff).getPrediction().values.flatten())
pd.DataFrame(simPrice).T.plot(ax=ax, color='r')
ax.get_legend().remove()

plt.savefig('../Investment Research_N/smallcases/Model smallcase/Cash/LM/' +rebalDate +'_Pred12_SC100Df.png')

#%%

# 3months -----------

qFR14IC = arma.ModelSelection(qFR14.values.flatten(), 5, 5).getICseries()
qFR14IC.sort_values("BIC").head()

#%%

mod14 = arma.Model(qFR14, p = 0, q = 1)
# mod14 = arma.Model(qFR14, p = 1, q = 0)
# mod14 = arma.Model(qFR14, p = 3, q = 1)
mod14.getParams()

#%%

sims14 = arma.SimulateFD(mod14, init_Val=oFR.iloc[0].values.flatten(), repetition= rep).getFDValues()

#%%


fig, ax = plt.subplots(figsize=(24, 6))
simPrice14  = []
for i in range(rep):
    simPrice14.append(tsa.BackOperation(oRoi.values.flatten(), sims14.iloc[:, i], fraction= frCoff).getPrediction().values.flatten())
pd.DataFrame(simPrice14).T.plot(ax=ax, color='r')
ax.get_legend().remove()

plt.savefig('../Investment Research_N/smallcases/Model smallcase/Cash/LM/' +rebalDate +'_Pred14_SC100Df.png')


#%%

simulDf12 = pd.DataFrame(simPrice).T
simulDf14 = pd.DataFrame(simPrice14).T


#%%
# simulDf12.index = qRoi.index[0:simulDf12.index[-1]+1]
# simulDf14.index = qRoi.index[0:simulDf14.index[-1]+1]

#%%
# simulDf12 = pd.DataFrame(simPrice).T
# simulDf12.to_excel('../Investment Research_N/smallcases/Model smallcase/Cash/LM/SimulateDf.xlsx')

#%%



#%%

resultDf.loc[rebalDate]['Ret_Avg'] = np.mean(simulDf12.apply(lambda x : (x[35] / x[13])-1))
resultDf.loc[rebalDate]['Std_Avg'] = np.mean(simulDf12.apply(lambda x : np.std(x.pct_change(1))))
resultDf.loc[rebalDate]['Avg_Ret'] = (simulDf12.mean(1)[35] / simulDf12.mean(1)[0]) - 1
resultDf.loc[rebalDate]['Avg_Std'] = simulDf12.mean(1).pct_change(1).std()
stDf.loc[rebalDate]['12'] = np.mean(simulDf12.pct_change(1).std())

                                        
#%%

resultDf14.loc[rebalDate]['Ret_Avg'] = np.mean(simulDf14.apply(lambda x : (x[35] / x[13])-1))
resultDf14.loc[rebalDate]['Std_Avg'] = np.mean(simulDf14.apply(lambda x : np.std(x.pct_change(1))))
resultDf14.loc[rebalDate]['Avg_Ret'] = (simulDf14.mean(1)[35] / simulDf14.mean(1)[0]) - 1
resultDf14.loc[rebalDate]['Avg_Std'] = simulDf14.mean(1).pct_change(1).std()
stDf.loc[rebalDate]['14'] = np.mean(simulDf14.pct_change(1).std())

#%%

print(resultDf)
print(resultDf14)
print(stDf)


#%%

resultDf.to_excel('../Investment Research_N/smallcases/Model smallcase/Cash/LM/12_SC100Df.xlsx') 
resultDf14.to_excel('../Investment Research_N/smallcases/Model smallcase/Cash/LM/14_SC100Df.xlsx')
stDf.to_excel('../Investment Research_N/smallcases/Model smallcase/Cash/LM/STD_SC100Df.xlsx')

                                            
#%%

stDf = pd.DataFrame(index = rebalDates, columns = ['12', '14'])                                             










