import {getExampleNumber,isPossiblePhoneNumber,isSupportedCountry,validatePhoneNumberLength} from 'libphonenumber-js';
import type {CountryCode} from 'libphonenumber-js';
import examples from 'libphonenumber-js/examples.mobile.json';
import {countries} from './countries';

export function countryForCallingCode(code:string){
  return countries.find(([,callingCode])=>callingCode===code)?.[0]||'Pakistan';
}

export function phoneFormat(country:string){
  const option=countries.find(([name])=>name===country)||countries.find(([name])=>name==='Pakistan')!;
  const countryCode:CountryCode=isSupportedCountry(option[3])?option[3] as CountryCode:'PK';
  const example=getExampleNumber(countryCode,examples)?.nationalNumber||'1234567890';
  return {callingCode:option[1],countryCode,example,digits:example.length};
}

export function phoneNumberError(country:string,number:string){
  const format=phoneFormat(country);
  const internationalNumber=`${format.callingCode}${number}`;
  const problem=validatePhoneNumberLength(internationalNumber);
  if(problem==='TOO_SHORT'||problem==='INVALID_LENGTH')return `Enter a valid ${country} number. Example: ${format.example}`;
  if(problem==='TOO_LONG')return `This ${country} number is too long. Example: ${format.example}`;
  if(!isPossiblePhoneNumber(internationalNumber))return `Enter a valid ${country} number. Example: ${format.example}`;
  return '';
}
