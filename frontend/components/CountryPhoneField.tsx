'use client';
import {useState} from 'react';
import {AsYouType} from 'libphonenumber-js';
import {countries} from '@/lib/countries';
import {countryForCallingCode,phoneFormat,phoneNumberError} from '@/lib/phone';

export function CountryPhoneField({defaultCountryCode='+92',defaultValue='',label='Phone number'}:{
  defaultCountryCode?:string;
  defaultValue?:string;
  label?:string;
}){
  const [country,setCountry]=useState(countryForCallingCode(defaultCountryCode));
  const [number,setNumber]=useState(defaultValue);
  const selectedCountry=countries.find(([name])=>name===country)||countries[0];
  const callingCode=selectedCountry[1];
  const format=phoneFormat(country);
  const formattedNumber=number?new AsYouType(format.countryCode).input(number):'';
  return <label className="form-field">{label}<span className="auth-phone">
    <span className="phone-prefix" aria-label={`Country calling code ${callingCode}`}><span>{selectedCountry[2]}</span><b>{callingCode}</b></span>
    <select aria-label="Phone country" value={country} onChange={event=>{event.currentTarget.parentElement?.querySelector<HTMLInputElement>('.phone-number-input')?.setCustomValidity('');setCountry(event.target.value)}}>
      {countries.map(([name,code,flag])=><option key={`${name}-${code}`} value={name}>{flag} {name}</option>)}
    </select>
    <input type="hidden" name="phone_country_code" value={callingCode}/>
    <input className="phone-number-input" type="tel" inputMode="tel" autoComplete="tel-national"
      required aria-label={`${label}, national number`} placeholder={format.example} value={formattedNumber}
      onBlur={event=>event.currentTarget.setCustomValidity(phoneNumberError(country,number))}
      onChange={event=>{const digits=event.target.value.replace(/[^0-9]/g,'');event.currentTarget.setCustomValidity(phoneNumberError(country,digits));setNumber(digits)}}/>
    <input type="hidden" name="phone_number" value={number}/>
  </span><small>Flag and {callingCode} update with your country. Example: {format.example} · {format.digits} digits</small></label>;
}
