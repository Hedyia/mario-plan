import React from "react";

const FormInput = ({ name, title, handleChange, ...otherProps }) => {
  return (
    <div className="input-field">
      <label htmlFor={name}>{title}</label>
      <input name={name} onChange={handleChange} {...otherProps} />
    </div>
  );
};

export default FormInput;
