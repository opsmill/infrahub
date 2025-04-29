import React from 'react';
import ReactPlayer from 'react-player/youtube';

export default function VideoPlayer({ url }) {
  return (
    <div style={{
      border: '3px solid #eee',
      borderRadius: '12px',
      padding: '8px',
      backgroundColor: '#fafafa',
      margin: '2rem 0',
      maxWidth: '800px'
    }}>
      <div style={{ position: 'relative', paddingTop: '56.25%' }}>
        <ReactPlayer
          url={url}
          style={{ position: 'absolute', top: 0, left: 0 }}
          width="100%"
          height="100%"
          controls
        />
      </div>
    </div>
  );
}
