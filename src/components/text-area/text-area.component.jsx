import React from "react";

const TextArea = ({ handleChange, name, title, value }) => {
  return (
    <div className="input-field">
      <label htmlFor={name}>{title}</label>
      <textarea
        name={name}
        value={value}
        onChange={handleChange}
        className="materialize-textarea"
      ></textarea>
    </div>
  );
};

export default TextArea;
