"""Preserve source values; all transformations produce an explicit audit trail."""
import copy
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

POLICY=Path(__file__).with_name('policy.json')

class AdaptationError(ValueError): pass


def number(value):
    if isinstance(value,bool):raise AdaptationError('NUMBER_INVALID')
    try:result=Decimal(str(value))
    except InvalidOperation as error:raise AdaptationError('NUMBER_INVALID') from error
    if not result.is_finite() or result<0:raise AdaptationError('NUMBER_INVALID')
    return result


class ProductAdapter:
    def __init__(self, configuration=None, evidence_resolver=None):
        self.configuration=configuration or json.loads(POLICY.read_text())
        self.units=self.configuration['units']
        self.evidence_resolver=evidence_resolver

    def verified_external(self, record):
        if not record or not self.evidence_resolver or not record.get('source_id'):return False
        expected={k:v for k,v in record.items() if k not in ('source_id','evidence_verified')}
        return self.evidence_resolver(record['source_id'])==expected

    def canonical(self, unit):
        return self.configuration.get('unit_aliases',{}).get(unit,unit)

    def quantity(self,value,unit,target):
        original_unit,original_target=unit,target
        unit,target=self.canonical(unit),self.canonical(target)
        if unit not in self.units or target not in self.units:raise AdaptationError('UNSUPPORTED_UNIT')
        a,b=self.units[unit],self.units[target]
        if a['dimension']!=b['dimension']:raise AdaptationError('INCOMPATIBLE_UNIT_DIMENSIONS')
        factor=Decimal(a['factor'])/Decimal(b['factor'])
        return number(value)*factor,{'from_unit':original_unit,'to_unit':original_target,'factor':str(factor),
                                    'reference':self.configuration.get('conversion_reference')}

    def nutrient(self,fact,target_basis,target_unit,density=None):
        raw=copy.deepcopy(fact);basis=fact.get('basis',{})
        if not basis.get('state') or basis['state']!=target_basis.get('state'):raise AdaptationError('STATE_OR_PREPARATION_MISMATCH')
        numerator,numerator_trace=self.quantity(fact['value'],fact['unit'],target_unit)
        try:denominator,basis_trace=self.quantity(basis['amount'],basis['unit'],target_basis['unit'])
        except AdaptationError as error:
            if str(error)!='INCOMPATIBLE_UNIT_DIMENSIONS':raise
            if not self.verified_external(density):raise AdaptationError('DENSITY_EVIDENCE_REQUIRED')
            rho=number(density['g_per_ml'])
            if rho<=0:raise AdaptationError('DENSITY_INVALID')
            from_dimension=self.units[self.canonical(basis['unit'])]['dimension'];to_dimension=self.units[self.canonical(target_basis['unit'])]['dimension']
            if {from_dimension,to_dimension}!={'mass','volume'}:raise AdaptationError('INCOMPATIBLE_BASIS')
            canonical='g' if from_dimension=='mass' else 'ml'
            amount,_=self.quantity(basis['amount'],basis['unit'],canonical)
            transformed=amount/rho if from_dimension=='mass' else amount*rho
            denominator,unit_trace=self.quantity(transformed,'ml' if to_dimension=='volume' else 'g',target_basis['unit'])
            basis_trace={'density':copy.deepcopy(density),'unit_conversion':unit_trace}
        if denominator<=0:raise AdaptationError('BASIS_INVALID')
        value=numerator*number(target_basis['amount'])/denominator
        return {'raw_record':raw,'value':float(value),'unit':target_unit,'basis':copy.deepcopy(target_basis),
                'derivation':{'numerator':numerator_trace,'basis_conversion':basis_trace,
                              'formula':'converted_nutrient * target_basis_amount / converted_source_basis_amount'}}

    def price(self,fact,target_quantity=None,target_currency=None,fx=None):
        raw=copy.deepcopy(fact);currency=fact.get('unit')
        if not isinstance(currency,str) or not re.fullmatch('[A-Z]{3}',currency):raise AdaptationError('CURRENCY_INVALID')
        if not fact.get('date') or not fact.get('channel'):raise AdaptationError('PRICE_SOURCE_CONTEXT_REQUIRED')
        value=number(fact['value']);target_currency=target_currency or currency;traces=[]
        if any(c not in self.configuration.get('currencies',[]) for c in (currency,target_currency)):raise AdaptationError('CURRENCY_CONFIGURATION_REQUIRED')
        if currency!=target_currency:
            if not self.verified_external(fx) or not fx.get('date') or fx.get('from')!=currency or fx.get('to')!=target_currency:
                raise AdaptationError('FX_EVIDENCE_REQUIRED')
            if number(fx['rate'])<=0:raise AdaptationError('FX_INVALID')
            value*=number(fx['rate']);traces.append({'fx':copy.deepcopy(fx)})
        pack=fact.get('quantity') or ({'amount':fact['volume_ml'],'unit':'ml','count':1} if 'volume_ml' in fact else None)
        if not pack or number(pack.get('count',1))<=0:raise AdaptationError('PACK_SPECIFICATION_REQUIRED')
        if target_quantity:
            quantity,trace=self.quantity(pack['amount'],pack['unit'],target_quantity['unit'])
            quantity*=number(pack.get('count',1))
            if quantity<=0:raise AdaptationError('PACK_SPECIFICATION_REQUIRED')
            value*=number(target_quantity['amount'])/quantity;traces.append({'quantity_conversion':trace,'pack_count':pack.get('count',1)})
        return {'raw_record':raw,'value':float(value),'currency':target_currency,
                'comparison_quantity':copy.deepcopy(target_quantity or pack),'derivation':traces}
