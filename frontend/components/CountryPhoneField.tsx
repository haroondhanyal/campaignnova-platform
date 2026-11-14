'use client';
import {useState} from 'react';
import {Phone} from 'lucide-react';
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
  return <label className="form-field">{label}<span className="auth-phone">
    <select aria-label="Phone country" value={country} onChange={event=>{event.currentTarget.parentElement?.querySelector<HTMLInputElement>('input[name="phone_number"]')?.setCustomValidity('');setCountry(event.target.value);setNumber('')}}>
      {countries.map(([name,code,flag])=><option key={`${name}-${code}`} value={name}>{flag} {name} ({code})</option>)}
    </select>
    <input type="hidden" name="phone_country_code" value={callingCode}/>
    <Phone size={16}/>
    <input name="phone_number" type="tel" inputMode="numeric" pattern="[0-9]*" autoComplete="tel-national"
      minLength={7} maxLength={15} required placeholder={format.example} value={number}
      onBlur={event=>event.currentTarget.setCustomValidity(phoneNumberError(country,number))}
      onChange={event=>{const digits=event.target.value.replace(/[^0-9]/g,'');event.currentTarget.setCustomValidity(phoneNumberError(country,digits));setNumber(digits)}}/>
  </span><small>Country format example: {format.example} · {format.digits} digits</small></label>;
}
