# ! pip install arch

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# plt.style.use('seaborn')
import arch

import warnings

warnings.filterwarnings('ignore')


class Volatility:
    def __init__(self, p=0, q=None):
        self.p = p
        self.q = q
        self.cls = arch.univariate

    def getConstant(self):
        vol = self.cls.ConstantVariance()
        return vol

    def getARCH(self):
        vol = self.cls.ARCH(p=self.p)
        return vol

    def getGARCH(self):
        # garch specific parameter
        asym = 0
        power = 2
        # garch object
        vol = self.cls.GARCH(p=self.p, q=self.q, power=power, o=asym)
        return vol

    def getEGARCH(self):
        # Egarch specific parameter
        asym = 0
        # Egarch object
        vol = self.cls.EGARCH(p=self.p, q=self.q, o=asym)
        return vol

    def getFIGARCH(self, trunc=1000):
        # Figarch sepecific parameter
        power = 2
        # Figarch object
        vol = self.cls.FIGARCH(p=self.p, q=self.q, power=power, truncation=trunc)
        return vol


class Distribution:
    def __init__(self):
        self.cls = arch.univariate

    def getNormal(self):
        dist = self.cls.Normal()
        return dist

    def getT(self):
        dist = self.cls.StudentsT()
        return dist


class Mean:
    def __init__(self, Data, hold=0, lags=1):
        self.data = Data
        self.cls = arch.univariate
        self.hold = hold
        self.lag = lags

    def getZeroMean(self):
        mean = self.cls.ZeroMean(self.data, hold_back=self.hold)
        return mean

    def getConstantMean(self):
        mean = self.cls.ConstantMean(self.data, hold_back=self.hold)
        return mean

    def getAR(self, constant=True):
        mean = self.cls.ARX(self.data, lags=self.lag, hold_back=self.hold, constant=constant)
        return mean

class Model:
    def __init__(self, Data , mean='Constant', hold=0, vol='ARCH', p=1, q=None, dist='Normal', lags=1, consAR=True, truncation=1000):
        self.data = Data
        self.hold = hold
        self.mean = mean
        self.vol = vol
        self.dist = dist
        self.cons = consAR
        self.p = p
        self.q = q
        self.trunc = truncation
        self.lag = lags

        # Calculating mean
        if self.mean == 'Constant':
            model = Mean(self.data, hold=self.hold).getConstantMean()
        elif self.mean == 'Zero':
            model = Mean(self.data, hold=self.hold).getZeroMean()
        elif self.mean == 'AR':
            model = Mean(self.data, hold=self.hold, lags=self.lag).getAR(constant=self.cons)
        else:
            raise TypeError('Choose among ("Constant", "Zero", "AR")!')

        # Calculating volatility
        if self.vol == 'Constant':
            model.volatility = Volatility().getConstant()
        elif self.vol == 'ARCH':
            model.volatility = Volatility(p=self.p).getARCH()
        elif self.vol == 'GARCH':
            if self.q is None:
                raise ValueError('Choose q!')
            model.volatility = Volatility(p=self.p, q=self.q).getGARCH()
        elif self.vol == 'EGARCH':
            if self.q is None:
                raise ValueError('Choose q!')
            model.volatility = Volatility(p=self.p, q=self.q).getEGARCH()
        elif self.vol == 'FIGARCH':
            if self.q is None:
                raise ValueError('Choose q!')
            model.volatility = Volatility(p=self.p, q=self.q).getFIGARCH(trunc=self.trunc)
        else:
            raise TypeError('Choose among ("Constant","ARCH", "GARCH", "EGARCH", "FIGARCH")!')

        # Specifying Distribution of residuals
        if self.dist == 'Normal':
            model.distribution = Distribution().getNormal()
        elif self.dist == 'StudentsT':
            model.distribution = Distribution().getT()
        else:
            raise TypeError('Choose among ("Normal" , "StudentsT")!')

        # Model fitting
        self.model = model.fit(disp='off')

        # FIGARCH-specific: store fractional differencing parameter if applicable
        if self.vol == 'FIGARCH':
            self.d = self.model.params.get('d', None)
        else:
            self.d = None

    def getParameters(self):
        param = self.model.params
        tstat = self.model.tvalues
        pvalue = self.model.pvalues
        std = self.model.std_err
        res = pd.DataFrame([param, tstat, pvalue, std]).T
        return res

    def getStatistics(self):
        aic = self.model.aic
        bic = self.model.bic
        r2 = self.model.rsquared
        scale = self.model.scale
        llk = self.model.loglikelihood
        res = pd.Series([aic, bic, r2, scale, llk], index=['aic', 'bic', 'r2', 'scale', 'loglikelihood'])
        return res

    def getVolatilityValues(self):
        mod = self.model
        cond = mod.conditional_volatility
        std_res = mod.std_resid
        resid = mod.resid
        res = pd.DataFrame([cond, resid, std_res]).T
        return res


class SimulateVariance:
    def __init__(self, model, Data=None, init_Val=None, nSim=22, nRep=30):
        if Data is None and init_Val is None:
            raise ValueError("Both Data and init_Val can't simultaneously be None")

        self.data = Data
        self.model = model
        self.nSim = nSim
        self.nRep = nRep

        # Initialize starting values
        if init_Val is not None:
            self.init = init_Val
            if len(self.init) != self.model.p:
                raise ValueError(f'Length of init must be {self.model.p}')
        else:
            self.init = self.data[:self.model.p].values.flatten()

        # Extract parameters
        self.param = self.model.model.params
        self.alpha = self.param[-self.model.p - (self.model.q or 0):- (self.model.q or 0)].values
        self.beta = self.param[-self.model.q:].values if self.model.vol in ['GARCH', 'EGARCH'] else None
        self.d = getattr(self.model, 'd', None)  # FIGARCH fractional differencing

        # Generate shocks for simulation
        self.e = [np.random.randn(self.nSim) for _ in range(self.nRep)]

    def predict(self, coef, history):
        """Linear prediction based on coefficients and history"""
        yhat = 0
        coef = np.array(coef)
        for i in range(len(coef)):
            yhat += coef[i] * history[-i - 1]
        return yhat

    def fractional_weights(self, d, n):
        """Compute fractional differencing weights for FIGARCH"""
        w = np.zeros(n)
        w[0] = 1
        for k in range(1, n):
            w[k] = w[k - 1] * ((k - 1 - d) / k)
        return w

    def getValues(self):
        predictions = []

        for j in range(self.nRep):
            pred = list(self.init)
            ej = self.e[j]

            if self.d is not None:  # FIGARCH simulation
                weights = self.fractional_weights(self.d, self.nSim)
                for i in range(self.nSim):
                    eps_hist = np.array(pred[-len(weights):]) ** 2
                    frac_term = np.sum(weights[:len(eps_hist)] * eps_hist)
                    garch_term = self.predict(self.beta, pred) if self.beta is not None else 0
                    pred.append(self.param['omega'] + frac_term + garch_term)
            else:  # ARCH/GARCH simulation
                eps = np.convolve(pred, ej ** 2, mode='valid')
                for i in range(self.nSim):
                    if self.beta is not None:
                        pred.append(self.param['omega'] + self.predict(self.beta, pred) +
                                    self.predict(self.alpha, eps[:i + self.alpha.shape[0]]))
                    else:
                        pred.append(self.param['omega'] + self.predict(self.alpha, eps[:i + self.alpha.shape[0]]))

            predictions.append(pred)

        var = pd.DataFrame(predictions).T

        if self.data is not None:
            var['index'] = self.data.index[:self.nSim + self.init.shape[0]]
            var = var.set_index('index')

        return var

    def plot(self, Axes=None):
        df = self.getValues()
        if Axes is None:
            fig, ax = plt.subplots(1, figsize=(24, 6))
        else:
            ax = Axes
        df.plot(ax=ax, color='r', alpha=0.3)
        if self.data is not None:
            self.data[:self.nSim + self.init.shape[0]].plot(ax=ax, color='k')
        ax.get_legend().remove()
